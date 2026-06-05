"""CLI-level tests — verify wiring between commands and lower-level behaviour.

A small in-test fake DataSource replaces the deleted FixtureSource. It's
monkeypatched in place of MT5Source so poll() can run without MetaTrader5
installed and without network/keychain access.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mt5_pnl_exporter import snapshot
from mt5_pnl_exporter.cli import app
from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
)
from mt5_pnl_exporter.sources.base import AccountInfo

runner = CliRunner()

_SAMPLE_FIXTURE = Path(__file__).parent / "fixtures" / "sample_snapshot.json"


def _load_sample() -> Snapshot:
    return Snapshot.model_validate(json.loads(_SAMPLE_FIXTURE.read_text()))


class _FakeSource:
    """In-test DataSource fake. Returns canned data per login; raises for fail_logins."""

    def __init__(
        self,
        accounts: dict[int, AccountInfo] | None = None,
        closed_deals: dict[int, list[ClosedDeal]] | None = None,
        open_positions: dict[int, list[OpenPosition]] | None = None,
        cash_flows: dict[int, list[CashFlow]] | None = None,
        fail_logins: set[int] | None = None,
    ) -> None:
        self._accounts = accounts or {}
        self._closed = closed_deals or {}
        self._open = open_positions or {}
        self._flows = cash_flows or {}
        self._fail = fail_logins or set()
        self.shutdown_called = False

    def _check(self, login: int) -> None:
        if login in self._fail:
            raise RuntimeError(f"fake failure for login {login}")

    def account_info(self, login: int) -> AccountInfo:
        self._check(login)
        if login not in self._accounts:
            raise RuntimeError(f"No fake account for login {login}")
        return self._accounts[login]

    def fetch_closed_deals(self, login: int, _from: int, _to: int) -> list[ClosedDeal]:
        self._check(login)
        return self._closed.get(login, [])

    def fetch_open_positions(self, login: int) -> list[OpenPosition]:
        self._check(login)
        return self._open.get(login, [])

    def fetch_cash_flows(self, login: int, _from: int, _to: int) -> list[CashFlow]:
        self._check(login)
        return self._flows.get(login, [])

    def shutdown(self) -> None:
        self.shutdown_called = True


def _fake_from_sample() -> _FakeSource:
    """A _FakeSource pre-populated from the canonical sample fixture."""
    snap = _load_sample()
    accounts = {
        a.login: AccountInfo(
            login=a.login,
            label=a.label,
            currency=a.currency,
            balance=a.balance,
            equity=a.equity,
        )
        for a in snap.accounts
    }
    closed: dict[int, list[ClosedDeal]] = {}
    for d in snap.closed_deals:
        closed.setdefault(d.account, []).append(d)
    open_: dict[int, list[OpenPosition]] = {}
    for p in snap.open_positions:
        open_.setdefault(p.account, []).append(p)
    flows: dict[int, list[CashFlow]] = {}
    for c in snap.cash_flows:
        flows.setdefault(c.account, []).append(c)
    return _FakeSource(
        accounts=accounts, closed_deals=closed, open_positions=open_, cash_flows=flows
    )


TEST_PASSPHRASE = "test-passphrase"


@pytest.fixture
def install_fake(monkeypatch):
    """Returns a factory: install_fake(fake) replaces MT5Source + secrets in cli."""

    def _install(fake: _FakeSource) -> _FakeSource:
        monkeypatch.setattr(
            "mt5_pnl_exporter.cli.MT5Source",
            lambda *a, **kw: fake,
        )
        # resolve_passwords would hit the keychain; short-circuit it
        monkeypatch.setattr(
            "mt5_pnl_exporter.cli.resolve_passwords",
            lambda cfg: {a.login: "pw" for a in cfg.accounts},
        )
        # encryption passphrase would hit the keychain too
        monkeypatch.setattr(
            "mt5_pnl_exporter.cli.get_encryption_passphrase",
            lambda: TEST_PASSPHRASE,
        )
        return fake

    return _install


def _write_cfg(path: Path, snapshot_path: str, accounts: list[tuple[str, int]]) -> None:
    lines = [
        f"snapshot_path: '{snapshot_path}'\n",
        "terminal_path: 'C:\\\\fake\\\\terminal64.exe'\n",
        "accounts:\n",
    ]
    for label, login in accounts:
        lines += [
            f"  - label: '{label}'\n",
            f"    login: {login}\n",
            "    server: 'TestBroker-Live'\n",
        ]
    path.write_text("".join(lines))


# ─── perms ───────────────────────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_poll_warns_on_world_readable_config(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json.gz.age"), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o644)
    install_fake(_fake_from_sample())
    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert "chmod 600" in result.output, result.output


# ─── poll happy path ─────────────────────────────────────────────────────────


def test_poll_writes_snapshot_with_all_record_types(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567), ("Scalper EA", 7654321)])
    os.chmod(cfg_path, 0o600)
    install_fake(_fake_from_sample())

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.output

    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    assert snap.schema_version == "1.0"
    assert {a.login for a in snap.accounts} == {1234567, 7654321}
    assert len(snap.closed_deals) == 5
    assert len(snap.open_positions) == 2
    assert len(snap.cash_flows) == 2


# ─── poll error handling / carry-forward ─────────────────────────────────────


def test_poll_carries_forward_last_success_on_failure(tmp_path, install_fake):
    """Failing account keeps last_success from prior; succeeding account updates it."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567), ("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    snapshot.write(
        snap_path,
        Snapshot(
            schema_version="1.0",
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=1234567,
                    label="Trend EA",
                    currency="USD",
                    balance=500.0,
                    equity=500.0,
                    last_success="2025-01-01T00:00:00Z",
                    last_error=None,
                ),
                AccountSnapshot(
                    login=99998,
                    label="Bad",
                    currency="USD",
                    balance=200.0,
                    equity=200.0,
                    last_success="2025-01-01T00:00:00Z",
                    last_error=None,
                ),
            ],
            closed_deals=[],
            open_positions=[],
            cash_flows=[],
        ),
        TEST_PASSPHRASE,
    )

    fake = _fake_from_sample()
    fake._fail = {99998}
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1

    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    by_login = {a.login: a for a in snap.accounts}

    known = by_login[1234567]
    assert known.last_error is None
    assert known.last_success is not None
    assert known.last_success != "2025-01-01T00:00:00Z"

    bad = by_login[99998]
    assert bad.last_error is not None
    assert bad.last_success == "2025-01-01T00:00:00Z"


def test_poll_keeps_prior_snapshot_when_all_fail(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    snapshot.write(
        snap_path,
        Snapshot(
            schema_version="1.0",
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=99998,
                    label="Bad",
                    currency="USD",
                    balance=100.0,
                    equity=100.0,
                    last_success="2025-01-01T00:00:00Z",
                    last_error=None,
                ),
            ],
            closed_deals=[],
            open_positions=[],
            cash_flows=[],
        ),
        TEST_PASSPHRASE,
    )
    prior_bytes = snap_path.read_bytes()

    fake = _FakeSource(fail_logins={99998})
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert snap_path.read_bytes() == prior_bytes


def test_poll_writes_errors_when_all_fail_no_prior(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    fake = _FakeSource(fail_logins={99998})
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert snap_path.exists()
    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    assert len(snap.accounts) == 1
    assert snap.accounts[0].last_error is not None
    assert snap.accounts[0].last_success is None


# ─── poll --config errors ────────────────────────────────────────────────────


def test_poll_config_not_found(tmp_path):
    missing = tmp_path / "nonexistent.yaml"
    result = runner.invoke(app, ["poll", "--config", str(missing)])
    assert result.exit_code != 0


# ─── poll src.shutdown() path ────────────────────────────────────────────────


def test_poll_shutdown_called_on_source(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o600)

    fake = _fake_from_sample()
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.output
    assert fake.shutdown_called


# ─── set-password ────────────────────────────────────────────────────────────


def test_set_password_empty_exits_nonzero():
    result = runner.invoke(app, ["set-password", "1234567"], input="\n")
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_set_password_stores_password(monkeypatch):
    stored: dict[int, str] = {}

    def fake_set(login: int, pw: str) -> None:
        stored[login] = pw

    monkeypatch.setattr("mt5_pnl_exporter.cli.set_investor_password", fake_set)
    result = runner.invoke(app, ["set-password", "1234567"], input="s3cr3t\n")
    assert result.exit_code == 0, result.output
    assert stored.get(1234567) == "s3cr3t"


# ─── poll missing encryption passphrase ──────────────────────────────────────


def test_poll_exits_when_encryption_passphrase_missing(tmp_path, monkeypatch):
    """Missing passphrase: exit 1 with the documented message, no MT5 call."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o600)

    fake = _fake_from_sample()
    monkeypatch.setattr("mt5_pnl_exporter.cli.MT5Source", lambda *a, **kw: fake)
    monkeypatch.setattr(
        "mt5_pnl_exporter.cli.resolve_passwords",
        lambda cfg: {a.login: "pw" for a in cfg.accounts},
    )
    monkeypatch.setattr(
        "mt5_pnl_exporter.cli.get_encryption_passphrase",
        lambda: None,
    )

    # Spy: assertion = the fake's account_info was never called.
    calls: list[int] = []
    original = fake.account_info
    fake.account_info = lambda login: (calls.append(login), original(login))[1]  # type: ignore[assignment]

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert "no encryption passphrase set in keychain" in result.output
    assert "mt5-pnl-exporter set-encryption-passphrase" in result.output
    assert calls == []
    assert not snap_path.exists()


# ─── set-encryption-passphrase ───────────────────────────────────────────────


def test_set_encryption_passphrase_empty_exits_nonzero():
    result = runner.invoke(app, ["set-encryption-passphrase"], input="\n\n")
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_set_encryption_passphrase_mismatch_exits_nonzero():
    result = runner.invoke(app, ["set-encryption-passphrase"], input="hunter2\ndifferent\n")
    assert result.exit_code != 0
    assert "match" in result.output.lower()


def test_set_encryption_passphrase_stores_on_success(monkeypatch):
    stored: dict[str, str] = {}

    def fake_set(passphrase: str) -> None:
        stored["pw"] = passphrase

    monkeypatch.setattr("mt5_pnl_exporter.cli.set_encryption_passphrase", fake_set)
    result = runner.invoke(app, ["set-encryption-passphrase"], input="hunter2\nhunter2\n")
    assert result.exit_code == 0, result.output
    assert stored.get("pw") == "hunter2"


def test_schema_command_writes_json_schema(tmp_path: Path) -> None:
    """`schema` writes the pydantic-generated JSON Schema with all top-level Snapshot fields."""
    output = tmp_path / "snapshot.schema.json"

    result = runner.invoke(app, ["schema", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    parsed = json.loads(output.read_text())

    # Real schema, not stub output.
    assert parsed.get("title") == "Snapshot"

    # Every top-level Snapshot field is present. Regression-catching: if a field
    # is renamed or dropped without regenerating the committed schema file, this
    # fails meaningfully rather than just confirming "some JSON exists".
    expected_fields = {
        "schema_version",
        "generated_at",
        "accounts",
        "closed_deals",
        "open_positions",
        "cash_flows",
    }
    assert expected_fields <= parsed.get("properties", {}).keys()
