"""CLI-level tests — verify wiring between commands and lower-level behaviour."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from mt5_pnl_exporter import snapshot
from mt5_pnl_exporter.cli import app
from mt5_pnl_exporter.snapshot import AccountSnapshot, Snapshot

runner = CliRunner()

# Login 99998 is not in FixtureSource — always fails with "No fixture account"
_UNKNOWN_LOGIN = 99998


def _write_cfg(path: Path, snapshot_path: str, extra: str = "") -> None:
    path.write_text(
        f"snapshot_path: '{snapshot_path}'\n"
        "accounts:\n"
        "  - label: 'Test'\n"
        "    login: 1234567\n"
        "    server: 'TestBroker-Live'\n"
        "  - label: 'Test2'\n"
        "    login: 7654321\n"
        "    server: 'TestBroker-Live'\n" + extra
    )


def _write_cfg_logins(path: Path, snapshot_path: str, logins: list[tuple[str, int]]) -> None:
    lines = [f"snapshot_path: '{snapshot_path}'\n", "accounts:\n"]
    for label, login in logins:
        lines += [
            f"  - label: '{label}'\n",
            f"    login: {login}\n",
            "    server: 'TestBroker-Live'\n",
        ]
    path.write_text("".join(lines))


# ─── perms ───────────────────────────────────────────────────────────────────


def test_poll_warns_on_world_readable_config(tmp_path):
    """poll should emit the perms warning to stderr for a world-readable config.yaml."""
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json"))
    os.chmod(cfg_path, 0o644)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path), "--source", "fixture"])
    # CliRunner mixes stderr into output by default; Rich prints to sys.stderr.
    assert "chmod 600" in result.output, result.output


# ─── poll lifecycle ──────────────────────────────────────────────────────────


def _prior_snapshot(snap_path: Path, login: int, last_success: str) -> None:
    """Write a minimal prior snapshot for a single account."""
    snapshot.write(
        snap_path,
        Snapshot(
            schema_version=1,
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=login,
                    label="Test",
                    currency="USD",
                    balance=1000.0,
                    equity=1000.0,
                    last_success=last_success,
                    last_error=None,
                )
            ],
            daily=[],
        ),
    )


def test_poll_carries_forward_last_success_on_failure(tmp_path):
    """Failing account keeps last_success from prior snapshot; succeeding account updates it."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg_logins(cfg_path, str(snap_path), [("Known", 1234567), ("Unknown", _UNKNOWN_LOGIN)])
    os.chmod(cfg_path, 0o600)

    # Write a prior snapshot with both accounts, unknown has a last_success
    snapshot.write(
        snap_path,
        Snapshot(
            schema_version=1,
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=1234567,
                    label="Known",
                    currency="USD",
                    balance=500.0,
                    equity=500.0,
                    last_success="2025-01-01T00:00:00Z",
                    last_error=None,
                ),
                AccountSnapshot(
                    login=_UNKNOWN_LOGIN,
                    label="Unknown",
                    currency="USD",
                    balance=200.0,
                    equity=200.0,
                    last_success="2025-01-01T00:00:00Z",
                    last_error=None,
                ),
            ],
            daily=[],
        ),
    )

    result = runner.invoke(app, ["poll", "--config", str(cfg_path), "--source", "fixture"])
    assert result.exit_code == 1  # one account failed

    snap = snapshot.read(snap_path)
    by_login = {a.login: a for a in snap.accounts}

    known = by_login[1234567]
    assert known.last_error is None
    assert known.last_success is not None
    assert known.last_success != "2025-01-01T00:00:00Z"  # updated to current run

    unknown = by_login[_UNKNOWN_LOGIN]
    assert unknown.last_error is not None
    assert unknown.last_success == "2025-01-01T00:00:00Z"  # carried from prior


def test_poll_keeps_prior_snapshot_when_all_fail(tmp_path):
    """When every account fails and a prior snapshot exists, the prior is kept unchanged."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg_logins(cfg_path, str(snap_path), [("Unknown", _UNKNOWN_LOGIN)])
    os.chmod(cfg_path, 0o600)
    _prior_snapshot(snap_path, _UNKNOWN_LOGIN, "2025-01-01T00:00:00Z")
    prior_text = snap_path.read_text()

    result = runner.invoke(app, ["poll", "--config", str(cfg_path), "--source", "fixture"])
    assert result.exit_code == 1
    assert snap_path.read_text() == prior_text


def test_poll_writes_errors_when_all_fail_no_prior(tmp_path):
    """When every account fails and no prior snapshot exists, a snapshot with errors is written."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg_logins(cfg_path, str(snap_path), [("Unknown", _UNKNOWN_LOGIN)])
    os.chmod(cfg_path, 0o600)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path), "--source", "fixture"])
    assert result.exit_code == 1
    assert snap_path.exists()
    snap = snapshot.read(snap_path)
    assert len(snap.accounts) == 1
    assert snap.accounts[0].last_error is not None
    assert snap.accounts[0].last_success is None


# ─── poll --config error paths ────────────────────────────────────────────────


def test_poll_config_not_found(tmp_path):
    """poll with a missing --config file exits non-zero with a helpful message."""
    missing = tmp_path / "nonexistent.yaml"
    result = runner.invoke(app, ["poll", "--config", str(missing), "--source", "fixture"])
    assert result.exit_code != 0
    assert (
        "not found" in result.output.lower()
        or "no such file" in result.output.lower()
        or result.exception is not None
    )


# ─── poll src.shutdown() path ────────────────────────────────────────────────


def test_poll_shutdown_called_on_source(tmp_path, monkeypatch):
    """poll calls src.shutdown() on sources that implement it."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg(cfg_path, str(snap_path))
    os.chmod(cfg_path, 0o600)

    shutdown_called = []

    # Patch FixtureSource to add a shutdown method so the hasattr branch is hit
    from mt5_pnl_exporter.sources import fixture as fixture_module

    original_class = fixture_module.FixtureSource

    class FixtureSourceWithShutdown(original_class):
        def shutdown(self):
            shutdown_called.append(True)

    monkeypatch.setattr(fixture_module, "FixtureSource", FixtureSourceWithShutdown)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path), "--source", "fixture"])
    assert result.exit_code == 0, result.output
    assert shutdown_called, "shutdown() was not called"


# ─── set-password ─────────────────────────────────────────────────────────────


def test_set_password_empty_exits_nonzero():
    """set-password exits 1 with an error when the user enters an empty password."""
    result = runner.invoke(app, ["set-password", "1234567"], input="\n")
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_set_password_stores_password(monkeypatch):
    """set-password calls set_investor_password when a non-empty password is entered."""
    stored: dict[int, str] = {}

    def fake_set(login: int, pw: str) -> None:
        stored[login] = pw

    monkeypatch.setattr("mt5_pnl_exporter.cli.set_investor_password", fake_set)
    result = runner.invoke(app, ["set-password", "1234567"], input="s3cr3t\n")
    assert result.exit_code == 0, result.output
    assert stored.get(1234567) == "s3cr3t"
