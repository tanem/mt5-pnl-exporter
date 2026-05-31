# Phase 1b Cycle 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `mt5-pnl-exporter`'s pre-aggregated `DailyRow` snapshot with raw `ClosedDeal` / `OpenPosition` / `CashFlow` records, drop the now-redundant `aggregate.py` / `FixtureSource` / `--source` flag / `poll:` config wrapper, and bump `SCHEMA_VERSION` to `2`.

**Architecture:** Snapshot models grow from two to four record types — `AccountSnapshot` unchanged, `DailyRow` replaced by `ClosedDeal` (full MT5 `TradeDeal` fields), `OpenPosition` (full MT5 `TradePosition` fields), `CashFlow` (same shape as `ClosedDeal`, balance-family records). `DataSource` protocol grows from one fetcher to three. `MT5Source` memoises `history_deals_get` across the closed-deal + cash-flow calls. All MT5 enum-ish integer fields are kept raw. Config flattens — no `poll:` wrapper.

**Tech Stack:** Python 3.12, pydantic 2, Typer, pytest with coverage, ruff, mypy, uv. Working directory throughout this plan: `/Users/tane/Code/mt5-pnl-exporter` (a separate repo from the one this plan lives in).

**Reference spec:** [`docs/superpowers/specs/2026-06-01-phase-1b-cycle-1-design.md`](../specs/2026-06-01-phase-1b-cycle-1-design.md).

**Note on intermediate test failures:** Between Tasks 1 and 4 the full test suite will have known failures because `cli.py` and `test_cli.py` reference symbols (`DailyRow`, `--source fixture`, `cfg.poll.terminal_path`) that disappear progressively. Each task only verifies tests relevant to its own scope. Task 7 runs the entire suite green.

---

## File Structure (final state)

```
src/mt5_pnl_exporter/
├── cli.py              # rewritten: no --source, uses 3 fetchers, terminal_path top-level
├── config.py           # flattened: terminal_path on Config; PollConfig deleted
├── secrets.py          # unchanged
├── snapshot.py         # rewritten: ClosedDeal, OpenPosition, CashFlow; SCHEMA_VERSION = 2
└── sources/
    ├── base.py         # rewritten: 3-fetcher protocol; balance-family constants added
    └── mt5.py          # rewritten: 3 fetchers + history_deals_get cache

(DELETED)
src/mt5_pnl_exporter/aggregate.py
src/mt5_pnl_exporter/sources/fixture.py

tests/
├── fixtures/
│   └── sample_snapshot.json    # NEW (replaces sample_deals.json)
├── test_cli.py                 # rewritten: in-test fake DataSource
├── test_config.py              # rewritten: flattened shape
├── test_mt5_source.py          # extended: 3 fetchers, cache, field-copy fidelity
├── test_snapshot.py            # rewritten: new schema round-trip
├── test_schema_file.py         # unchanged
└── test_secrets.py             # unchanged

(DELETED)
tests/test_aggregate.py
tests/fixtures/sample_deals.json

schema/snapshot.schema.json     # regenerated from new models
README.md                       # light touch — see Task 6
CLAUDE.md                       # light touch — see Task 6
```

---

## Task 1: Snapshot models — `ClosedDeal`, `OpenPosition`, `CashFlow`

**Files:**
- Modify: `src/mt5_pnl_exporter/snapshot.py` (full rewrite)
- Modify: `tests/test_snapshot.py` (full rewrite)
- Modify: `schema/snapshot.schema.json` (regenerated)

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_snapshot.py` with:

```python
"""Tests for snapshot.py — round-trip, schema version guard, atomic write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.snapshot import (
    SCHEMA_VERSION,
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
    read,
    write,
)


def _account() -> AccountSnapshot:
    return AccountSnapshot(
        login=1234567,
        label="Test",
        currency="USD",
        balance=1000.0,
        equity=1000.0,
        last_success="2025-01-01T00:00:00Z",
        last_error=None,
    )


def _closed_deal(ticket: int = 1) -> ClosedDeal:
    return ClosedDeal(
        account=1234567,
        ticket=ticket,
        order=ticket * 10,
        position_id=ticket * 100,
        time=1700000000,
        time_msc=1700000000000,
        type=1,
        entry=1,
        reason=0,
        magic=0,
        volume=0.1,
        price=1.2345,
        profit=50.0,
        swap=-1.0,
        commission=-0.5,
        fee=0.0,
        symbol="EURUSD",
        comment="",
        external_id="",
    )


def _open_position(ticket: int = 1) -> OpenPosition:
    return OpenPosition(
        account=1234567,
        ticket=ticket,
        identifier=ticket * 1000,
        time=1700000000,
        time_msc=1700000000000,
        time_update=1700000500,
        time_update_msc=1700000500000,
        type=0,
        reason=0,
        magic=0,
        volume=0.2,
        price_open=1.1000,
        price_current=1.1050,
        sl=0.0,
        tp=0.0,
        profit=10.0,
        swap=0.0,
        symbol="EURUSD",
        comment="",
        external_id="",
    )


def _cash_flow(ticket: int = 1, amount: float = 1000.0) -> CashFlow:
    return CashFlow(
        account=1234567,
        ticket=ticket,
        order=0,
        position_id=0,
        time=1700000000,
        time_msc=1700000000000,
        type=2,
        entry=0,
        reason=0,
        magic=0,
        volume=0.0,
        price=0.0,
        profit=amount,
        swap=0.0,
        commission=0.0,
        fee=0.0,
        symbol="",
        comment="Deposit",
        external_id="",
    )


def _minimal_snapshot() -> Snapshot:
    return Snapshot(
        schema_version=2,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[_closed_deal()],
        open_positions=[_open_position()],
        cash_flows=[_cash_flow()],
    )


# ─── round-trip ──────────────────────────────────────────────────────────────


def test_write_read_roundtrip(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap = _minimal_snapshot()
    write(snap_path, snap)
    result = read(snap_path)
    assert result.schema_version == snap.schema_version
    assert result.generated_at == snap.generated_at
    assert len(result.accounts) == 1
    assert result.accounts[0].login == 1234567
    assert result.accounts[0].balance == 1000.0
    assert len(result.closed_deals) == 1
    assert result.closed_deals[0].ticket == 1
    assert result.closed_deals[0].profit == 50.0
    assert result.closed_deals[0].symbol == "EURUSD"
    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticket == 1
    assert result.open_positions[0].price_current == 1.1050
    assert len(result.cash_flows) == 1
    assert result.cash_flows[0].profit == 1000.0
    assert result.cash_flows[0].comment == "Deposit"


def test_empty_collections_roundtrip(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap = Snapshot(
        schema_version=2,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[],
        open_positions=[],
        cash_flows=[],
    )
    write(snap_path, snap)
    result = read(snap_path)
    assert result.closed_deals == []
    assert result.open_positions == []
    assert result.cash_flows == []


def test_write_sets_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    assert raw["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == 2


# ─── schema version guard ────────────────────────────────────────────────────


def test_read_rejects_wrong_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    raw["schema_version"] = SCHEMA_VERSION - 1
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path)


def test_read_rejects_missing_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    del raw["schema_version"]
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path)


def test_read_error_mentions_repoll(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    raw["schema_version"] = 999
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="poll"):
        read(snap_path)


def test_read_rejects_corrupt_json(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text("{not valid json")
    with pytest.raises(ValueError, match="corrupt"):
        read(snap_path)


def test_read_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="poll"):
        read(tmp_path / "nonexistent.json")


# ─── atomic write ────────────────────────────────────────────────────────────


def test_write_no_tmp_file_after_success(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    tmp = snap_path.with_suffix(".tmp")
    assert not tmp.exists()
    assert snap_path.exists()


def test_write_failure_leaves_destination_unchanged(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    original = _minimal_snapshot()
    write(snap_path, original)
    original_text = snap_path.read_text()

    modified = Snapshot(
        schema_version=2,
        generated_at="2025-06-01T00:00:00Z",
        accounts=original.accounts,
        closed_deals=original.closed_deals,
        open_positions=original.open_positions,
        cash_flows=original.cash_flows,
    )
    with (
        patch.object(Path, "replace", side_effect=OSError("simulated rename failure")),
        pytest.raises(OSError),
    ):
        write(snap_path, modified)

    assert snap_path.read_text() == original_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_snapshot.py -v`
Expected: FAIL with `ImportError: cannot import name 'CashFlow'` (or similar) — the new model symbols don't exist yet.

- [ ] **Step 3: Rewrite `snapshot.py`**

Replace the entire contents of `src/mt5_pnl_exporter/snapshot.py` with:

```python
"""Snapshot read/write — atomic temp+rename so a reader never sees a partial file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 2


class AccountSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    login: int
    label: str
    currency: str
    balance: float
    equity: float
    last_success: str | None
    last_error: str | None


class ClosedDeal(BaseModel):
    """One closing trade deal — every field MT5's TradeDeal emits, plus `account`."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    account: int  # login — added by the exporter; MT5 deals don't carry it
    ticket: int
    order: int
    position_id: int
    time: int  # Unix seconds (close time)
    time_msc: int  # Unix milliseconds
    type: int  # mt5 DEAL_TYPE_* (raw integer)
    entry: int  # mt5 DEAL_ENTRY_* (raw integer)
    reason: int  # mt5 DEAL_REASON_*
    magic: int
    volume: float
    price: float
    profit: float
    swap: float
    commission: float
    fee: float
    symbol: str
    comment: str
    external_id: str


class OpenPosition(BaseModel):
    """One currently-open position — every field MT5's TradePosition emits, plus `account`."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    account: int
    ticket: int
    identifier: int
    time: int  # Unix seconds (open time)
    time_msc: int
    time_update: int  # Unix seconds (last update time)
    time_update_msc: int
    type: int  # mt5 POSITION_TYPE_*
    reason: int  # mt5 POSITION_REASON_*
    magic: int
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    symbol: str
    comment: str
    external_id: str


class CashFlow(BaseModel):
    """One balance-family deal (deposit/withdrawal/credit/charge/correction/bonus/commission).

    Same shape as ClosedDeal — these ARE deals, distinguished only by `type`.
    Fields that don't apply to balance records (volume, price, symbol, entry,
    position_id) come through as 0 / empty string from MT5.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    account: int
    ticket: int
    order: int
    position_id: int
    time: int
    time_msc: int
    type: int  # mt5 DEAL_TYPE_BALANCE / CREDIT / CHARGE / CORRECTION / BONUS / COMMISSION
    entry: int
    reason: int
    magic: int
    volume: float
    price: float
    profit: float  # the cash amount — positive (deposit/credit) or negative (withdrawal/charge)
    swap: float
    commission: float
    fee: float
    symbol: str
    comment: str
    external_id: str


class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2]
    generated_at: str
    accounts: list[AccountSnapshot]
    closed_deals: list[ClosedDeal]
    open_positions: list[OpenPosition]
    cash_flows: list[CashFlow]


def write(path: Path, snap: Snapshot) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(snap.model_dump_json(indent=2))
    tmp.replace(path)


def read(path: Path) -> Snapshot:
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {path}\n"
            "Run 'mt5-pnl-exporter poll' on the Windows host first to generate it."
        )
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Snapshot file is corrupt at {path}; re-run 'mt5-pnl-exporter poll' to regenerate."
        ) from exc
    version = data.get("schema_version", 0)
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Snapshot schema_version {version} != expected {SCHEMA_VERSION}. "
            "Re-run 'mt5-pnl-exporter poll' to regenerate."
        )
    return Snapshot.model_validate(data)
```

- [ ] **Step 4: Run snapshot tests to verify they pass**

Run: `uv run pytest tests/test_snapshot.py -v`
Expected: all tests pass.

- [ ] **Step 5: Regenerate the JSON Schema file**

Run: `uv run mt5-pnl-exporter schema`
Expected: `Wrote schema/snapshot.schema.json` printed.

- [ ] **Step 6: Verify the schema staleness check passes**

Run: `uv run pytest tests/test_schema_file.py -v`
Expected: passes.

- [ ] **Step 7: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add src/mt5_pnl_exporter/snapshot.py tests/test_snapshot.py schema/snapshot.schema.json
git commit -m "feat: snapshot models — ClosedDeal, OpenPosition, CashFlow (schema v2)

Replaces DailyRow with raw per-deal/per-position records. Every field
MT5's TradeDeal/TradePosition emits, integers kept as raw integers,
plus the exporter-added 'account' (login). CashFlow shares ClosedDeal's
shape — they are the same MT5 deal record distinguished only by type.
Bumps SCHEMA_VERSION 1 → 2 and regenerates the JSON Schema file."
```

---

## Task 2: Sources rewrite — `DataSource` protocol + `MT5Source`

**Files:**
- Modify: `src/mt5_pnl_exporter/sources/base.py` (full rewrite)
- Modify: `src/mt5_pnl_exporter/sources/mt5.py` (full rewrite)
- Modify: `tests/test_mt5_source.py` (extend with new fetchers + cache test; existing tests adapt)

- [ ] **Step 1: Write the failing tests for the new fetchers**

Replace the entire contents of `tests/test_mt5_source.py` with:

```python
"""Tests for MT5Source — the live data backend.

CLAUDE.md prefers fixtures over mocking MT5, but the bugs fixed in
e233fc9 and subsequent commits were specifically in the shape of the
mt5.initialize() and mt5.login() calls — exactly the kind of issue a
JSON fixture can't catch. A minimal in-memory shim for the MetaTrader5
module is justified here, scoped to call-signature contracts and
field-copy fidelity.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_fake_mt5(
    login_ok: bool = True,
    init_ok: bool = True,
    history_total_values: list[int] | None = None,
    history_deals: list | None = None,
    positions: list | None = None,
) -> types.ModuleType:
    """Register a fake MetaTrader5 module so MT5Source can import it."""
    fake = types.ModuleType("MetaTrader5")
    fake.calls: list[tuple[str, tuple, dict]] = []  # type: ignore[attr-defined]
    _total_iter = iter(history_total_values or [])
    _total_default = 0 if history_total_values is None else None

    def initialize(*args: Any, **kwargs: Any) -> bool:
        fake.calls.append(("initialize", args, kwargs))  # type: ignore[attr-defined]
        return init_ok

    def login(*args: Any, **kwargs: Any) -> bool:
        fake.calls.append(("login", args, kwargs))  # type: ignore[attr-defined]
        return login_ok

    def last_error() -> tuple[int, str]:
        return (-6, "Terminal: Authorization failed")

    def shutdown() -> None:
        fake.calls.append(("shutdown", (), {}))  # type: ignore[attr-defined]

    def history_deals_total(*args: Any, **kwargs: Any) -> int:
        val = next(_total_iter, _total_default)
        fake.calls.append(("history_deals_total", args, kwargs))  # type: ignore[attr-defined]
        return val if val is not None else 0

    def history_deals_get(*args: Any, **kwargs: Any) -> list:
        fake.calls.append(("history_deals_get", args, kwargs))  # type: ignore[attr-defined]
        return list(history_deals or [])

    def positions_get(*args: Any, **kwargs: Any) -> list:
        fake.calls.append(("positions_get", args, kwargs))  # type: ignore[attr-defined]
        return list(positions or [])

    class _AccountInfo:
        currency = "USD"
        balance = 1000.0
        equity = 1000.0

    def account_info() -> _AccountInfo:
        return _AccountInfo()

    fake.initialize = initialize  # type: ignore[attr-defined]
    fake.login = login  # type: ignore[attr-defined]
    fake.last_error = last_error  # type: ignore[attr-defined]
    fake.shutdown = shutdown  # type: ignore[attr-defined]
    fake.history_deals_total = history_deals_total  # type: ignore[attr-defined]
    fake.history_deals_get = history_deals_get  # type: ignore[attr-defined]
    fake.positions_get = positions_get  # type: ignore[attr-defined]
    fake.account_info = account_info  # type: ignore[attr-defined]

    sys.modules["MetaTrader5"] = fake
    return fake


@pytest.fixture
def fake_mt5():
    fake = _install_fake_mt5()
    yield fake
    sys.modules.pop("MetaTrader5", None)


def _make_deal(**kwargs: Any) -> types.SimpleNamespace:
    """Build a fake MT5 TradeDeal-shaped record with default zero/empty fields."""
    defaults = dict(
        ticket=0, order=0, position_id=0, time=0, time_msc=0,
        type=0, entry=0, reason=0, magic=0,
        volume=0.0, price=0.0,
        profit=0.0, swap=0.0, commission=0.0, fee=0.0,
        symbol="", comment="", external_id="",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_position(**kwargs: Any) -> types.SimpleNamespace:
    """Build a fake MT5 TradePosition-shaped record with default zero/empty fields."""
    defaults = dict(
        ticket=0, identifier=0, time=0, time_msc=0, time_update=0, time_update_msc=0,
        type=0, reason=0, magic=0,
        volume=0.0, price_open=0.0, price_current=0.0, sl=0.0, tp=0.0,
        profit=0.0, swap=0.0,
        symbol="", comment="", external_id="",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ── initialize() call shape ───────────────────────────────────────────────────


def test_initialize_passes_credentials(fake_mt5):
    """First call must pass login/password/server to initialize(), not just path."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.account_info(514248)

    inits = [c for c in fake_mt5.calls if c[0] == "initialize"]
    assert len(inits) == 1
    _, args, kwargs = inits[0]
    assert args == ("C:\\fake\\terminal64.exe",)
    assert kwargs["login"] == 514248
    assert kwargs["password"] == "inv-pw"
    assert kwargs["server"] == "BlackBull-Live"


def test_initialize_called_once_second_account_uses_login(fake_mt5):
    """After initialize(), switching accounts must call login() not initialize() again."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source(
        "C:\\fake\\terminal64.exe",
        {514248: "inv-pw-a", 999999: "inv-pw-b"},
        {514248: "BlackBull-Live", 999999: "BlackBull-Live"},
    )
    src.account_info(514248)
    src.account_info(999999)

    inits = [c for c in fake_mt5.calls if c[0] == "initialize"]
    logins = [c for c in fake_mt5.calls if c[0] == "login"]

    assert len(inits) == 1
    assert len(logins) == 1
    assert logins[0][1] == (999999,)
    assert logins[0][2] == {"password": "inv-pw-b", "server": "BlackBull-Live"}


def test_initialize_failure_surfaces_mt5_error(monkeypatch):
    _install_fake_mt5(init_ok=False)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match=r"MT5 initialize failed:.*-6"):
            src.account_info(514248)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── guards for missing config ─────────────────────────────────────────────────


def test_raises_when_server_missing(fake_mt5):
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {})
    with pytest.raises(RuntimeError, match="No server configured for login 514248"):
        src.account_info(514248)


def test_raises_when_password_missing(fake_mt5):
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {}, {514248: "BlackBull-Live"})
    with pytest.raises(RuntimeError, match="No investor password for login 514248"):
        src.account_info(514248)


def test_login_failure_surfaces_mt5_error(monkeypatch):
    _install_fake_mt5(login_ok=False)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source(
            "C:\\fake\\terminal64.exe",
            {514248: "inv-pw-a", 999999: "inv-pw-b"},
            {514248: "BlackBull-Live", 999999: "BlackBull-Live"},
        )
        src.account_info(514248)
        with pytest.raises(RuntimeError, match=r"MT5 login failed for 999999"):
            src.account_info(999999)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── history sync wait ────────────────────────────────────────────────────────


def test_history_sync_waits_for_stability(monkeypatch):
    totals = [0, 0, 3, 5, 7, 7, 7]
    fake = _install_fake_mt5(history_total_values=totals)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 0.0)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        src.fetch_closed_deals(514248, 0, 1)

        total_calls = [c for c in fake.calls if c[0] == "history_deals_total"]
        get_calls = [c for c in fake.calls if c[0] == "history_deals_get"]
        assert len(total_calls) >= 7
        assert get_calls
        total_idxs = [i for i, c in enumerate(fake.calls) if c[0] == "history_deals_total"]
        get_idx = next(i for i, c in enumerate(fake.calls) if c[0] == "history_deals_get")
        assert get_idx > max(total_idxs)
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_history_sync_zero_trades_returns_quickly(monkeypatch):
    fake = _install_fake_mt5()
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 0.0)
    try:
        from mt5_pnl_exporter.sources.mt5 import _HISTORY_SYNC_STABLE_POLLS, MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_closed_deals(514248, 0, 1)

        assert result == []
        total_calls = [c for c in fake.calls if c[0] == "history_deals_total"]
        assert len(total_calls) == _HISTORY_SYNC_STABLE_POLLS
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_history_sync_timeout_raises(monkeypatch):
    fake = _install_fake_mt5()
    counter = [0]

    def ever_growing(*args: Any, **kwargs: Any) -> int:
        counter[0] += 1
        fake.calls.append(("history_deals_total", args, kwargs))
        return counter[0]

    fake.history_deals_total = ever_growing

    tick = [0]

    def fake_monotonic() -> float:
        tick[0] += 1
        return float(tick[0]) * 10.0

    fake_time = types.SimpleNamespace(monotonic=fake_monotonic, sleep=lambda s: None)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5.time", fake_time)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_MAX_S", 5.0)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="history sync did not settle"):
            src.fetch_closed_deals(514248, 0, 1)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── history_deals_get() None handling ────────────────────────────────────────


def test_fetch_closed_deals_returns_empty_when_none_and_no_error():
    fake = _install_fake_mt5()
    fake.history_deals_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (1, "ERR_SUCCESS")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_closed_deals(514248, 0, 1)
        assert result == []
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_closed_deals_raises_when_none_and_mt5_error():
    fake = _install_fake_mt5()
    fake.history_deals_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (-10004, "Invalid timeout")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="history_deals_get failed"):
            src.fetch_closed_deals(514248, 0, 1)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── deal filtering (closed vs cash flow) ─────────────────────────────────────


def test_fetch_closed_deals_keeps_only_closing_non_balance():
    """Balance deals and non-closing entries dropped from closed_deals."""
    from mt5_pnl_exporter.sources.base import (
        DEAL_ENTRY_INOUT,
        DEAL_ENTRY_OUT,
        DEAL_TYPE_BALANCE,
    )

    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_IN = 0

    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BALANCE, entry=DEAL_ENTRY_OUT),  # dropped — balance
        _make_deal(ticket=2, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_IN),  # dropped — opening
        _make_deal(ticket=3, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, profit=50.0),  # kept
        _make_deal(ticket=4, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_INOUT, profit=-2.0),  # kept
    ]
    _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_closed_deals(514248, 0, 1)
        tickets = sorted(d.ticket for d in result)
        assert tickets == [3, 4]
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_cash_flows_keeps_only_balance_family():
    """Only DEAL_TYPE_BALANCE-family records land in cash_flows."""
    from mt5_pnl_exporter.sources.base import (
        DEAL_TYPE_BALANCE,
        DEAL_TYPE_BONUS,
        DEAL_TYPE_CHARGE,
        DEAL_TYPE_COMMISSION,
        DEAL_TYPE_CORRECTION,
        DEAL_TYPE_CREDIT,
    )

    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_OUT = 1

    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, profit=50.0),  # dropped
        _make_deal(ticket=2, type=DEAL_TYPE_BALANCE, profit=1000.0, comment="Deposit"),
        _make_deal(ticket=3, type=DEAL_TYPE_CREDIT, profit=10.0),
        _make_deal(ticket=4, type=DEAL_TYPE_CHARGE, profit=-1.0),
        _make_deal(ticket=5, type=DEAL_TYPE_CORRECTION, profit=0.5),
        _make_deal(ticket=6, type=DEAL_TYPE_BONUS, profit=5.0),
        _make_deal(ticket=7, type=DEAL_TYPE_COMMISSION, profit=-0.25),
    ]
    _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_cash_flows(514248, 0, 1)
        tickets = sorted(d.ticket for d in result)
        assert tickets == [2, 3, 4, 5, 6, 7]
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── field-copy fidelity ──────────────────────────────────────────────────────


def test_fetch_closed_deals_copies_every_field():
    """All TradeDeal fields land on ClosedDeal with values unchanged, plus account=login."""
    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_OUT = 1
    deal = _make_deal(
        ticket=987654321,
        order=12345,
        position_id=987654,
        time=1700000000,
        time_msc=1700000000123,
        type=DEAL_TYPE_BUY,
        entry=DEAL_ENTRY_OUT,
        reason=4,
        magic=42,
        volume=0.10,
        price=1.23456,
        profit=125.50,
        swap=-1.20,
        commission=-0.55,
        fee=0.10,
        symbol="EURUSD",
        comment="closed by SL",
        external_id="ext-1",
    )
    _install_fake_mt5(history_deals=[deal])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_closed_deals(514248, 0, 1)

        assert len(result) == 1
        d = result[0]
        assert d.account == 514248
        assert d.ticket == 987654321
        assert d.order == 12345
        assert d.position_id == 987654
        assert d.time == 1700000000
        assert d.time_msc == 1700000000123
        assert d.type == DEAL_TYPE_BUY
        assert d.entry == DEAL_ENTRY_OUT
        assert d.reason == 4
        assert d.magic == 42
        assert d.volume == 0.10
        assert d.price == 1.23456
        assert d.profit == 125.50
        assert d.swap == -1.20
        assert d.commission == -0.55
        assert d.fee == 0.10
        assert d.symbol == "EURUSD"
        assert d.comment == "closed by SL"
        assert d.external_id == "ext-1"
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_cash_flows_copies_every_field():
    from mt5_pnl_exporter.sources.base import DEAL_TYPE_BALANCE

    deal = _make_deal(
        ticket=111,
        order=0,
        position_id=0,
        time=1700000000,
        time_msc=1700000000000,
        type=DEAL_TYPE_BALANCE,
        entry=0,
        reason=0,
        magic=0,
        volume=0.0,
        price=0.0,
        profit=5000.0,
        swap=0.0,
        commission=0.0,
        fee=0.0,
        symbol="",
        comment="Initial deposit",
        external_id="dep-001",
    )
    _install_fake_mt5(history_deals=[deal])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_cash_flows(514248, 0, 1)

        assert len(result) == 1
        c = result[0]
        assert c.account == 514248
        assert c.ticket == 111
        assert c.type == DEAL_TYPE_BALANCE
        assert c.profit == 5000.0
        assert c.comment == "Initial deposit"
        assert c.external_id == "dep-001"
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_open_positions_copies_every_field():
    """All TradePosition fields land on OpenPosition with values unchanged, plus account=login."""
    POSITION_TYPE_SELL = 1
    pos = _make_position(
        ticket=555,
        identifier=555000,
        time=1700000000,
        time_msc=1700000000123,
        time_update=1700000500,
        time_update_msc=1700000500456,
        type=POSITION_TYPE_SELL,
        reason=0,
        magic=42,
        volume=0.25,
        price_open=1.2345,
        price_current=1.2300,
        sl=1.2400,
        tp=1.2200,
        profit=12.50,
        swap=-0.30,
        symbol="GBPUSD",
        comment="grid",
        external_id="ext-pos-1",
    )
    _install_fake_mt5(positions=[pos])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_open_positions(514248)

        assert len(result) == 1
        p = result[0]
        assert p.account == 514248
        assert p.ticket == 555
        assert p.identifier == 555000
        assert p.time == 1700000000
        assert p.time_msc == 1700000000123
        assert p.time_update == 1700000500
        assert p.time_update_msc == 1700000500456
        assert p.type == POSITION_TYPE_SELL
        assert p.reason == 0
        assert p.magic == 42
        assert p.volume == 0.25
        assert p.price_open == 1.2345
        assert p.price_current == 1.2300
        assert p.sl == 1.2400
        assert p.tp == 1.2200
        assert p.profit == 12.50
        assert p.swap == -0.30
        assert p.symbol == "GBPUSD"
        assert p.comment == "grid"
        assert p.external_id == "ext-pos-1"
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_open_positions_handles_none():
    """positions_get() returning None means no open positions, not an error."""
    fake = _install_fake_mt5()
    fake.positions_get = lambda *a, **k: None  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_open_positions(514248)
        assert result == []
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── history_deals_get cache ──────────────────────────────────────────────────


def test_history_deals_get_cached_across_closed_and_cash_flow_calls():
    """fetch_closed_deals then fetch_cash_flows for the same window must hit MT5 once."""
    from mt5_pnl_exporter.sources.base import DEAL_TYPE_BALANCE

    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_OUT = 1
    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, profit=10.0),
        _make_deal(ticket=2, type=DEAL_TYPE_BALANCE, profit=100.0),
    ]
    fake = _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        src.fetch_closed_deals(514248, 0, 1)
        src.fetch_cash_flows(514248, 0, 1)

        get_calls = [c for c in fake.calls if c[0] == "history_deals_get"]
        assert len(get_calls) == 1, f"expected 1 history_deals_get call, got {len(get_calls)}"
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_history_deals_get_cache_keyed_by_login_and_window():
    """Different (login, from, to) tuples each hit MT5 once."""
    fake = _install_fake_mt5(history_deals=[])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source(
            "C:\\fake\\terminal64.exe",
            {514248: "inv-pw", 999999: "inv-pw"},
            {514248: "BlackBull-Live", 999999: "BlackBull-Live"},
        )
        src.fetch_closed_deals(514248, 0, 100)
        src.fetch_closed_deals(514248, 0, 200)  # different window
        src.fetch_closed_deals(999999, 0, 100)  # different login

        get_calls = [c for c in fake.calls if c[0] == "history_deals_get"]
        assert len(get_calls) == 3
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_shutdown_clears_history_cache(fake_mt5):
    """shutdown() must clear the cache so a fresh poll re-fetches."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.fetch_closed_deals(514248, 0, 1)
    assert src._history_cache != {}
    src.shutdown()
    assert src._history_cache == {}


# ── account_info() None handling ─────────────────────────────────────────────


def test_account_info_raises_when_mt5_returns_none():
    fake = _install_fake_mt5()
    fake.account_info = lambda: None  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="account_info\\(\\) returned None for 514248"):
            src.account_info(514248)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── shutdown() ───────────────────────────────────────────────────────────────


def test_shutdown_calls_mt5_shutdown_when_initialized(fake_mt5):
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.account_info(514248)
    assert src._initialized
    src.shutdown()
    assert not src._initialized
    shutdown_calls = [c for c in fake_mt5.calls if c[0] == "shutdown"]
    assert len(shutdown_calls) == 1


def test_shutdown_is_noop_when_not_initialized(fake_mt5):
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.shutdown()
    shutdown_calls = [c for c in fake_mt5.calls if c[0] == "shutdown"]
    assert shutdown_calls == []


# ── slow-sync debug log ──────────────────────────────────────────────────────


def test_history_sync_slow_log_is_emitted(monkeypatch, caplog):
    import logging

    totals = [1, 2, 1, 2, 1, 2, 3, 3, 3]
    _install_fake_mt5(history_total_values=totals)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 1.0)

    mono_val = [0.0]

    def fake_monotonic() -> float:
        return mono_val[0]

    fake_time = types.SimpleNamespace(monotonic=fake_monotonic, sleep=lambda s: None)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5.time", fake_time)

    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with caplog.at_level(logging.DEBUG, logger="mt5_pnl_exporter.sources.mt5"):
            src.fetch_closed_deals(514248, 0, 1)
        assert any(
            "history sync" in r.message and "still in progress" in r.message for r in caplog.records
        )
    finally:
        sys.modules.pop("MetaTrader5", None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mt5_source.py -v`
Expected: FAIL — `fetch_closed_deals`, `fetch_open_positions`, `fetch_cash_flows`, `_history_cache`, balance-family constants don't exist yet.

- [ ] **Step 3: Rewrite `src/mt5_pnl_exporter/sources/base.py`**

Replace its entire contents with:

```python
"""DataSource protocol — swappable backend (MT5 today; future backends slot in here)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition

# MT5 deal-entry constants
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 3

# MT5 deal-type constants
# Trading deal types (used by ClosedDeal): 0 = buy, 1 = sell
# Balance-family types (used by CashFlow):
DEAL_TYPE_BALANCE = 2
DEAL_TYPE_CREDIT = 3
DEAL_TYPE_CHARGE = 4
DEAL_TYPE_CORRECTION = 5
DEAL_TYPE_BONUS = 6
DEAL_TYPE_COMMISSION = 7

# The full set of types that count as cash flows (balance family).
BALANCE_FAMILY_TYPES = frozenset(
    {
        DEAL_TYPE_BALANCE,
        DEAL_TYPE_CREDIT,
        DEAL_TYPE_CHARGE,
        DEAL_TYPE_CORRECTION,
        DEAL_TYPE_BONUS,
        DEAL_TYPE_COMMISSION,
    }
)


class AccountInfo(BaseModel):
    login: int
    label: str
    currency: str
    balance: float
    equity: float


@runtime_checkable
class DataSource(Protocol):
    def account_info(self, login: int) -> AccountInfo: ...
    def fetch_closed_deals(
        self, login: int, date_from: int, date_to: int
    ) -> list[ClosedDeal]: ...
    def fetch_open_positions(self, login: int) -> list[OpenPosition]: ...
    def fetch_cash_flows(
        self, login: int, date_from: int, date_to: int
    ) -> list[CashFlow]: ...
```

- [ ] **Step 4: Rewrite `src/mt5_pnl_exporter/sources/mt5.py`**

Replace its entire contents with:

```python
"""MT5Source — live data via the MetaTrader5 Python package (Windows only)."""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any

from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition
from mt5_pnl_exporter.sources.base import (
    BALANCE_FAMILY_TYPES,
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    AccountInfo,
)

logger = logging.getLogger(__name__)

# After mt5.login() the terminal downloads history asynchronously; poll until
# the deal count stabilises before calling history_deals_get().
_HISTORY_SYNC_POLL_S = 0.5
_HISTORY_SYNC_STABLE_POLLS = 3
_HISTORY_SYNC_MAX_S = 120.0


class MT5Source:
    def __init__(
        self,
        terminal_path: str,
        passwords: dict[int, str],
        servers: dict[int, str],
    ) -> None:
        try:
            import MetaTrader5 as mt5  # pragma: no cover
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "MetaTrader5 package not installed. "
                "Install with: uv sync --extra mt5  (Windows only)"
            ) from exc
        self._mt5 = mt5
        self._terminal_path = terminal_path
        self._passwords = passwords
        self._servers = servers
        self._initialized = False
        # Cache the raw history_deals_get result by (login, date_from, date_to)
        # so back-to-back fetch_closed_deals + fetch_cash_flows hit MT5 once.
        self._history_cache: dict[tuple[int, int, int], list[Any]] = {}

    def _connect(self, login: int) -> None:
        pw = self._passwords.get(login)
        if not pw:
            raise RuntimeError(f"No investor password for login {login}")
        server = self._servers.get(login)
        if not server:
            raise RuntimeError(f"No server configured for login {login}")
        if not self._initialized:
            ok = self._mt5.initialize(
                self._terminal_path,
                login=login,
                password=pw,
                server=server,
            )
            if not ok:
                err = self._mt5.last_error()
                raise RuntimeError(f"MT5 initialize failed: {err}")
            self._initialized = True
            return
        ok = self._mt5.login(login, password=pw, server=server)
        if not ok:
            err = self._mt5.last_error()
            raise RuntimeError(f"MT5 login failed for {login}: {err}")

    def _wait_history_synced(
        self,
        login: int,
        dt_from: datetime.datetime,
        dt_to: datetime.datetime,
    ) -> None:
        """Block until history_deals_total stabilises, indicating sync is done."""
        counts: list[int] = []
        deadline = time.monotonic() + _HISTORY_SYNC_MAX_S
        slow_logged = False
        while True:
            n = self._mt5.history_deals_total(dt_from, dt_to)
            counts.append(n)
            stable = counts[-_HISTORY_SYNC_STABLE_POLLS:]
            if len(counts) >= _HISTORY_SYNC_STABLE_POLLS and len(set(stable)) == 1:
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"MT5 history sync did not settle for {login} within {_HISTORY_SYNC_MAX_S}s"
                )
            elapsed = (len(counts) - 1) * _HISTORY_SYNC_POLL_S
            if not slow_logged and elapsed >= 5:
                logger.debug(
                    f"[mt5] history sync for {login} still in progress ({elapsed:.0f}s, count={n})"
                )
                slow_logged = True
            time.sleep(_HISTORY_SYNC_POLL_S)

    def _get_history_raw(
        self, login: int, date_from: int, date_to: int
    ) -> list[Any]:
        """Return the raw MT5 history_deals_get result for the window, cached."""
        key = (login, date_from, date_to)
        if key in self._history_cache:
            return self._history_cache[key]

        self._connect(login)
        dt_from = datetime.datetime.fromtimestamp(date_from, tz=datetime.UTC)
        dt_to = datetime.datetime.fromtimestamp(date_to, tz=datetime.UTC)
        self._wait_history_synced(login, dt_from, dt_to)
        raw = self._mt5.history_deals_get(dt_from, dt_to)
        if raw is None:
            code, msg = self._mt5.last_error()
            if code != 1:  # 1 = ERR_SUCCESS / no deals in range
                raise RuntimeError(
                    f"history_deals_get failed for {login}: ({code}, {msg!r})"
                )
            raw = []
        result = list(raw)
        self._history_cache[key] = result
        return result

    def fetch_closed_deals(
        self, login: int, date_from: int, date_to: int
    ) -> list[ClosedDeal]:
        raw = self._get_history_raw(login, date_from, date_to)
        out: list[ClosedDeal] = []
        for d in raw:
            if d.type in BALANCE_FAMILY_TYPES:
                continue
            if d.entry not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT):
                continue
            out.append(
                ClosedDeal(
                    account=login,
                    ticket=int(d.ticket),
                    order=int(d.order),
                    position_id=int(d.position_id),
                    time=int(d.time),
                    time_msc=int(d.time_msc),
                    type=int(d.type),
                    entry=int(d.entry),
                    reason=int(d.reason),
                    magic=int(d.magic),
                    volume=float(d.volume),
                    price=float(d.price),
                    profit=float(d.profit),
                    swap=float(d.swap),
                    commission=float(d.commission),
                    fee=float(getattr(d, "fee", 0.0)),
                    symbol=str(d.symbol),
                    comment=str(d.comment),
                    external_id=str(d.external_id),
                )
            )
        return out

    def fetch_cash_flows(
        self, login: int, date_from: int, date_to: int
    ) -> list[CashFlow]:
        raw = self._get_history_raw(login, date_from, date_to)
        out: list[CashFlow] = []
        for d in raw:
            if d.type not in BALANCE_FAMILY_TYPES:
                continue
            out.append(
                CashFlow(
                    account=login,
                    ticket=int(d.ticket),
                    order=int(d.order),
                    position_id=int(d.position_id),
                    time=int(d.time),
                    time_msc=int(d.time_msc),
                    type=int(d.type),
                    entry=int(d.entry),
                    reason=int(d.reason),
                    magic=int(d.magic),
                    volume=float(d.volume),
                    price=float(d.price),
                    profit=float(d.profit),
                    swap=float(d.swap),
                    commission=float(d.commission),
                    fee=float(getattr(d, "fee", 0.0)),
                    symbol=str(d.symbol),
                    comment=str(d.comment),
                    external_id=str(d.external_id),
                )
            )
        return out

    def fetch_open_positions(self, login: int) -> list[OpenPosition]:
        self._connect(login)
        raw = self._mt5.positions_get()
        if raw is None:
            return []
        out: list[OpenPosition] = []
        for p in raw:
            out.append(
                OpenPosition(
                    account=login,
                    ticket=int(p.ticket),
                    identifier=int(p.identifier),
                    time=int(p.time),
                    time_msc=int(p.time_msc),
                    time_update=int(p.time_update),
                    time_update_msc=int(p.time_update_msc),
                    type=int(p.type),
                    reason=int(p.reason),
                    magic=int(p.magic),
                    volume=float(p.volume),
                    price_open=float(p.price_open),
                    price_current=float(p.price_current),
                    sl=float(p.sl),
                    tp=float(p.tp),
                    profit=float(p.profit),
                    swap=float(p.swap),
                    symbol=str(p.symbol),
                    comment=str(p.comment),
                    external_id=str(p.external_id),
                )
            )
        return out

    def account_info(self, login: int) -> AccountInfo:
        self._connect(login)
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info() returned None for {login}")
        return AccountInfo(
            login=login,
            label=str(login),
            currency=info.currency,
            balance=float(info.balance),
            equity=float(info.equity),
        )

    def shutdown(self) -> None:
        if self._initialized:
            self._mt5.shutdown()
            self._initialized = False
        self._history_cache.clear()
```

- [ ] **Step 5: Run the source tests to verify they pass**

Run: `uv run pytest tests/test_mt5_source.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add src/mt5_pnl_exporter/sources/base.py src/mt5_pnl_exporter/sources/mt5.py tests/test_mt5_source.py
git commit -m "feat: DataSource protocol gains open positions + cash flows

DataSource now exposes fetch_closed_deals / fetch_open_positions /
fetch_cash_flows in place of fetch_deals. MT5Source copies every MT5
field 1:1 onto the new snapshot models, classifies balance-family
deal types as cash flows, and memoises history_deals_get per
(login, date_from, date_to) so the back-to-back closed-deal + cash-flow
fetches hit MT5 once. Adds balance-family deal-type constants."
```

---

## Task 3: Config flatten

**Files:**
- Modify: `src/mt5_pnl_exporter/config.py`
- Modify: `tests/test_config.py` (full rewrite)

- [ ] **Step 1: Read the current test_config.py to preserve its non-flatten coverage**

Run: `cat /Users/tane/Code/mt5-pnl-exporter/tests/test_config.py`
Expected: prints current test file. Read it to identify cases unrelated to `poll.terminal_path` (e.g. unique-labels, accounts-not-empty, keyring resolution, perms-check). These cases must survive the rewrite.

- [ ] **Step 2: Write the new test_config.py**

Replace the entire contents of `tests/test_config.py` with:

```python
"""Tests for config.py — flat shape (no poll: wrapper), validators, keyring."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.config import (
    AccountConfig,
    Config,
    check_file_perms,
    load_config,
    resolve_passwords,
)


def _write_cfg(path: Path, body: str) -> None:
    path.write_text(body)


# ─── flat shape ──────────────────────────────────────────────────────────────


def test_terminal_path_is_top_level(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "terminal_path: 'C:\\mt5\\terminal64.exe'\n"
        "accounts:\n"
        "  - label: Test\n"
        "    login: 1\n"
        "    server: TestBroker\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.terminal_path == "C:\\mt5\\terminal64.exe"
    assert cfg.snapshot_path == "/tmp/s.json"


def test_terminal_path_defaults_to_empty(tmp_path):
    """Omitting terminal_path is allowed; defaults to empty string."""
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "accounts:\n"
        "  - label: Test\n"
        "    login: 1\n"
        "    server: TestBroker\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.terminal_path == ""


# ─── validators ──────────────────────────────────────────────────────────────


def test_accounts_not_empty(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, "snapshot_path: /tmp/s.json\naccounts: []\n")
    with pytest.raises(ValueError, match="accounts"):
        load_config(cfg_path)


def test_labels_unique(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "accounts:\n"
        "  - label: Same\n"
        "    login: 1\n"
        "    server: A\n"
        "  - label: Same\n"
        "    login: 2\n"
        "    server: B\n",
    )
    with pytest.raises(ValueError, match="unique"):
        load_config(cfg_path)


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="config.example.yaml"):
        load_config(tmp_path / "nope.yaml")


# ─── perms ───────────────────────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_check_file_perms_warns_on_world_readable(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("x: 1\n")
    os.chmod(cfg_path, 0o644)
    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert "chmod 600" in captured.err


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_check_file_perms_silent_on_600(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("x: 1\n")
    os.chmod(cfg_path, 0o600)
    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert captured.err == ""


# ─── resolve_passwords ───────────────────────────────────────────────────────


def test_resolve_passwords_pulls_from_keyring():
    cfg = Config(
        snapshot_path="/tmp/s.json",
        terminal_path="",
        accounts=[
            AccountConfig(label="A", login=1, server="X"),
            AccountConfig(label="B", login=2, server="Y"),
        ],
    )
    with patch("mt5_pnl_exporter.config.get_investor_password") as gp:
        gp.side_effect = lambda login: f"pw-{login}"
        result = resolve_passwords(cfg)
    assert result == {1: "pw-1", 2: "pw-2"}


def test_resolve_passwords_raises_when_missing():
    cfg = Config(
        snapshot_path="/tmp/s.json",
        terminal_path="",
        accounts=[AccountConfig(label="A", login=1, server="X")],
    )
    with patch("mt5_pnl_exporter.config.get_investor_password", return_value=None):
        with pytest.raises(RuntimeError, match="set-password"):
            resolve_passwords(cfg)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `Config` model doesn't accept `terminal_path` at the top level yet (and likely still requires `poll:` shape).

- [ ] **Step 4: Rewrite `src/mt5_pnl_exporter/config.py`**

Replace its entire contents with:

```python
"""Config loading: pydantic models, keyring-first secret resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mt5_pnl_exporter.secrets import get_investor_password, redact_filter

_DEFAULT_CONFIG_PATH = Path("config.yaml")


class AccountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    login: int
    server: str


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_path: str
    terminal_path: str = ""
    accounts: list[AccountConfig]

    @field_validator("terminal_path", mode="before")
    @classmethod
    def _terminal_path_none_to_empty(cls, v: Any) -> str:
        return v or ""

    @field_validator("accounts")
    @classmethod
    def accounts_not_empty(cls, v: list[AccountConfig]) -> list[AccountConfig]:
        if not v:
            raise ValueError("accounts list must not be empty")
        return v

    @model_validator(mode="after")
    def _labels_unique(self) -> Config:
        labels = [a.label for a in self.accounts]
        if len(set(labels)) != len(labels):
            raise ValueError("account labels must be unique")
        return self


def check_file_perms(path: Path) -> None:
    """Warn if config has group/other-readable bits. Only call from poll."""
    if os.name == "nt":
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        from rich.console import Console

        Console(stderr=True).print(
            f"[yellow]Warning: {path} has permissions {oct(mode)} — should be 600. "
            "Run: chmod 600 config.yaml[/yellow]"
        )


def load_config(config_path: Path | None = None) -> Config:
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and fill in your values."
        )
    with path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return Config.model_validate(raw)


def resolve_passwords(cfg: Config) -> dict[int, str]:
    """Return {login: investor_password} from keyring; raise if any missing."""
    passwords: dict[int, str] = {}
    missing: list[str] = []
    for acct in cfg.accounts:
        pw = get_investor_password(acct.login)
        if not pw:
            missing.append(f"{acct.label} (login {acct.login})")
        else:
            redact_filter.register(pw)
            passwords[acct.login] = pw
    if missing:
        raise RuntimeError(
            "Investor password not found in keyring for: "
            + ", ".join(missing)
            + "\nRun: mt5-pnl-exporter set-password <login>"
        )
    return passwords
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: all pass.

- [ ] **Step 6: Update `config.example.yaml` if it exists**

Check whether `config.example.yaml` exists at the repo root and, if so, rewrite it to the flat shape. Use:

```bash
ls /Users/tane/Code/mt5-pnl-exporter/config.example.yaml
```

If present, replace its contents with:

```yaml
snapshot_path: ~/snapshots/mt5.json
terminal_path: C:\Program Files\MetaTrader 5\terminal64.exe
accounts:
  - label: Trend EA
    login: 1234567
    server: BrokerName-Live
  - label: Scalper EA
    login: 7654321
    server: BrokerName-Live
```

If the file does not exist, skip this step.

- [ ] **Step 7: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add src/mt5_pnl_exporter/config.py tests/test_config.py
[ -f config.example.yaml ] && git add config.example.yaml
git commit -m "refactor: flatten config — terminal_path at top level

With no query: section there is no peer to the poll: wrapper. Drops
PollConfig and moves terminal_path onto Config directly. extra='forbid'
on Config and AccountConfig means any stray legacy keys are rejected
by pydantic naturally — no migration shim."
```

---

## Task 4: CLI rewrite + new sample-snapshot fixture + test_cli rewrite

**Files:**
- Modify: `src/mt5_pnl_exporter/cli.py` (full rewrite of `poll` plus imports)
- Create: `tests/fixtures/sample_snapshot.json`
- Modify: `tests/test_cli.py` (full rewrite)

- [ ] **Step 1: Create the sample snapshot fixture**

Create `tests/fixtures/sample_snapshot.json` with:

```json
{
  "schema_version": 2,
  "generated_at": "2025-01-15T10:00:00Z",
  "accounts": [
    {
      "login": 1234567,
      "label": "Trend EA",
      "currency": "USD",
      "balance": 10240.50,
      "equity": 10198.20,
      "last_success": "2025-01-15T10:00:00Z",
      "last_error": null
    },
    {
      "login": 7654321,
      "label": "Scalper EA",
      "currency": "USD",
      "balance": 8910.00,
      "equity": 8874.50,
      "last_success": "2025-01-15T10:00:00Z",
      "last_error": null
    }
  ],
  "closed_deals": [
    {"account": 1234567, "ticket": 1001, "order": 5001, "position_id": 9001, "time": 1736899200, "time_msc": 1736899200000, "type": 0, "entry": 1, "reason": 0, "magic": 100, "volume": 0.10, "price": 1.0810, "profit": 25.50, "swap": -0.20, "commission": -0.50, "fee": 0.0, "symbol": "EURUSD", "comment": "tp hit", "external_id": ""},
    {"account": 1234567, "ticket": 1002, "order": 5002, "position_id": 9002, "time": 1736902800, "time_msc": 1736902800000, "type": 1, "entry": 1, "reason": 0, "magic": 100, "volume": 0.10, "price": 1.0825, "profit": -12.00, "swap": 0.0, "commission": -0.50, "fee": 0.0, "symbol": "EURUSD", "comment": "sl hit", "external_id": ""},
    {"account": 1234567, "ticket": 1003, "order": 5003, "position_id": 9003, "time": 1736906400, "time_msc": 1736906400000, "type": 0, "entry": 3, "reason": 0, "magic": 100, "volume": 0.20, "price": 1.0830, "profit": 40.00, "swap": -0.50, "commission": -1.00, "fee": 0.0, "symbol": "EURUSD", "comment": "", "external_id": ""},
    {"account": 7654321, "ticket": 2001, "order": 6001, "position_id": 10001, "time": 1736899800, "time_msc": 1736899800000, "type": 0, "entry": 1, "reason": 0, "magic": 200, "volume": 0.05, "price": 1.2705, "profit": 8.00, "swap": 0.0, "commission": -0.25, "fee": 0.0, "symbol": "GBPUSD", "comment": "", "external_id": ""},
    {"account": 7654321, "ticket": 2002, "order": 6002, "position_id": 10002, "time": 1736903400, "time_msc": 1736903400000, "type": 1, "entry": 1, "reason": 0, "magic": 200, "volume": 0.05, "price": 1.2720, "profit": -5.00, "swap": 0.0, "commission": -0.25, "fee": 0.0, "symbol": "GBPUSD", "comment": "", "external_id": ""}
  ],
  "open_positions": [
    {"account": 1234567, "ticket": 1100, "identifier": 9100, "time": 1736910000, "time_msc": 1736910000000, "time_update": 1736913600, "time_update_msc": 1736913600000, "type": 0, "reason": 0, "magic": 100, "volume": 0.10, "price_open": 1.0840, "price_current": 1.0855, "sl": 1.0820, "tp": 1.0880, "profit": 15.00, "swap": 0.0, "symbol": "EURUSD", "comment": "", "external_id": ""},
    {"account": 7654321, "ticket": 2100, "identifier": 10100, "time": 1736910600, "time_msc": 1736910600000, "time_update": 1736913600, "time_update_msc": 1736913600000, "type": 1, "reason": 0, "magic": 200, "volume": 0.05, "price_open": 1.2730, "price_current": 1.2725, "sl": 1.2745, "tp": 1.2710, "profit": 2.50, "swap": 0.0, "symbol": "GBPUSD", "comment": "", "external_id": ""}
  ],
  "cash_flows": [
    {"account": 1234567, "ticket": 500, "order": 0, "position_id": 0, "time": 1736000000, "time_msc": 1736000000000, "type": 2, "entry": 0, "reason": 0, "magic": 0, "volume": 0.0, "price": 0.0, "profit": 10000.00, "swap": 0.0, "commission": 0.0, "fee": 0.0, "symbol": "", "comment": "Initial deposit", "external_id": ""},
    {"account": 7654321, "ticket": 600, "order": 0, "position_id": 0, "time": 1736000000, "time_msc": 1736000000000, "type": 2, "entry": 0, "reason": 0, "magic": 0, "volume": 0.0, "price": 0.0, "profit": 9000.00, "swap": 0.0, "commission": 0.0, "fee": 0.0, "symbol": "", "comment": "Initial deposit", "external_id": ""}
  ]
}
```

- [ ] **Step 2: Write the failing tests (test_cli.py rewrite)**

Replace the entire contents of `tests/test_cli.py` with:

```python
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


@pytest.fixture
def install_fake(monkeypatch):
    """Returns a factory: install_fake(fake) replaces MT5Source in cli."""

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
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json"), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o644)
    install_fake(_fake_from_sample())
    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert "chmod 600" in result.output, result.output


# ─── poll happy path ─────────────────────────────────────────────────────────


def test_poll_writes_snapshot_with_all_record_types(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567), ("Scalper EA", 7654321)])
    os.chmod(cfg_path, 0o600)
    install_fake(_fake_from_sample())

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.output

    snap = snapshot.read(snap_path)
    assert snap.schema_version == 2
    assert {a.login for a in snap.accounts} == {1234567, 7654321}
    assert len(snap.closed_deals) == 5
    assert len(snap.open_positions) == 2
    assert len(snap.cash_flows) == 2


# ─── poll error handling / carry-forward ─────────────────────────────────────


def test_poll_carries_forward_last_success_on_failure(tmp_path, install_fake):
    """Failing account keeps last_success from prior; succeeding account updates it."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567), ("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    snapshot.write(
        snap_path,
        Snapshot(
            schema_version=2,
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=1234567, label="Trend EA", currency="USD",
                    balance=500.0, equity=500.0,
                    last_success="2025-01-01T00:00:00Z", last_error=None,
                ),
                AccountSnapshot(
                    login=99998, label="Bad", currency="USD",
                    balance=200.0, equity=200.0,
                    last_success="2025-01-01T00:00:00Z", last_error=None,
                ),
            ],
            closed_deals=[], open_positions=[], cash_flows=[],
        ),
    )

    fake = _fake_from_sample()
    fake._fail = {99998}
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1

    snap = snapshot.read(snap_path)
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
    snap_path = tmp_path / "snapshot.json"
    _write_cfg(cfg_path, str(snap_path), [("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    snapshot.write(
        snap_path,
        Snapshot(
            schema_version=2,
            generated_at="2025-01-01T00:00:00Z",
            accounts=[
                AccountSnapshot(
                    login=99998, label="Bad", currency="USD",
                    balance=100.0, equity=100.0,
                    last_success="2025-01-01T00:00:00Z", last_error=None,
                ),
            ],
            closed_deals=[], open_positions=[], cash_flows=[],
        ),
    )
    prior_text = snap_path.read_text()

    fake = _FakeSource(fail_logins={99998})
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert snap_path.read_text() == prior_text


def test_poll_writes_errors_when_all_fail_no_prior(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json"
    _write_cfg(cfg_path, str(snap_path), [("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    fake = _FakeSource(fail_logins={99998})
    install_fake(fake)

    result = runner.invoke(app, ["poll", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert snap_path.exists()
    snap = snapshot.read(snap_path)
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
    snap_path = tmp_path / "snapshot.json"
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `cli.py` still imports `aggregate`, still has `--source` flag, still uses `cfg.poll.terminal_path`, etc.

- [ ] **Step 4: Rewrite `src/mt5_pnl_exporter/cli.py`**

Replace its entire contents with:

```python
"""mt5-pnl-exporter CLI — poll | set-password | schema"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mt5_pnl_exporter import snapshot
from mt5_pnl_exporter.config import check_file_perms, load_config, resolve_passwords
from mt5_pnl_exporter.secrets import redact_filter, set_investor_password
from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
)
from mt5_pnl_exporter.sources.mt5 import MT5Source

app = typer.Typer(
    help="MT5 P&L exporter — poll deal history, write snapshot.json.",
    add_completion=False,
)
err = Console(stderr=True)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(redact_filter)
    logging.basicConfig(level=level, handlers=[handler], format="[%(levelname)s] %(message)s")


@app.command()
def poll(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Fetch deal history + open positions from MT5 and write snapshot.json."""
    _setup_logging(verbose)
    log = logging.getLogger(__name__)

    check_file_perms(config_path or Path("config.yaml"))
    cfg = load_config(config_path)
    snap_path = Path(cfg.snapshot_path)
    snap_path.parent.mkdir(parents=True, exist_ok=True)

    passwords = resolve_passwords(cfg)
    servers = {a.login: a.server for a in cfg.accounts}
    src = MT5Source(cfg.terminal_path, passwords, servers)

    now = datetime.datetime.now(tz=datetime.UTC)
    epoch_from = 0
    epoch_to = int(now.timestamp())

    prior_by_login: dict[int, AccountSnapshot] = {}
    try:
        prior = snapshot.read(snap_path)
        prior_by_login = {a.login: a for a in prior.accounts}
    except FileNotFoundError:
        pass

    accounts_out: list[AccountSnapshot] = []
    closed_deals_out: list[ClosedDeal] = []
    open_positions_out: list[OpenPosition] = []
    cash_flows_out: list[CashFlow] = []
    error_count = 0

    for acct in cfg.accounts:
        try:
            info = src.account_info(acct.login)
            deals = src.fetch_closed_deals(acct.login, epoch_from, epoch_to)
            flows = src.fetch_cash_flows(acct.login, epoch_from, epoch_to)
            positions = src.fetch_open_positions(acct.login)

            closed_deals_out.extend(deals)
            cash_flows_out.extend(flows)
            open_positions_out.extend(positions)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=info.currency,
                    balance=info.balance,
                    equity=info.equity,
                    last_success=now.isoformat().replace("+00:00", "Z"),
                    last_error=None,
                )
            )
            log.info(
                f"[poll] {acct.label} ({acct.login}): "
                f"{len(deals)} closed deals, {len(positions)} open, "
                f"{len(flows)} cash flows  OK"
            )
        except Exception as exc:
            error_count += 1
            log.error(f"[poll] {acct.label} ({acct.login}): FAILED — {exc}")
            prior_acct = prior_by_login.get(acct.login)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=prior_acct.currency if prior_acct else "",
                    balance=prior_acct.balance if prior_acct else 0.0,
                    equity=prior_acct.equity if prior_acct else 0.0,
                    last_success=prior_acct.last_success if prior_acct else None,
                    last_error=str(exc),
                )
            )

    try:
        if error_count == len(cfg.accounts) and prior_by_login:
            log.error(
                f"[poll] All {error_count} accounts failed; "
                f"keeping previous snapshot at {snap_path}."
            )
            raise SystemExit(1)

        snap = Snapshot(
            schema_version=2,
            generated_at=now.isoformat().replace("+00:00", "Z"),
            accounts=accounts_out,
            closed_deals=closed_deals_out,
            open_positions=open_positions_out,
            cash_flows=cash_flows_out,
        )
        snapshot.write(snap_path, snap)
        log.info(f"[poll] wrote {snap_path}  ({now.strftime('%Y-%m-%d %H:%M')})")
    finally:
        if hasattr(src, "shutdown"):
            src.shutdown()

    if error_count:
        raise SystemExit(1)


@app.command("set-password")
def set_password(
    login: Annotated[int, typer.Argument(help="MT5 account login number")],
) -> None:
    """Store an investor password in the OS keychain (never echoed to terminal)."""
    import getpass

    pw = getpass.getpass(f"Investor password for login {login}: ")
    if not pw:
        err.print("[red]Password cannot be empty.[/red]")
        raise SystemExit(1)
    set_investor_password(login, pw)
    err.print(f"[green]Password stored in keychain for login {login}.[/green]")


@app.command()
def schema(
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the JSON Schema file.")
    ] = Path("schema/snapshot.schema.json"),
) -> None:
    """Regenerate the JSON Schema for snapshot.json from the pydantic models."""
    schema_dict = Snapshot.model_json_schema()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema_dict, indent=2) + "\n")
    err.print(f"[green]Wrote {output}[/green]")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add src/mt5_pnl_exporter/cli.py tests/test_cli.py tests/fixtures/sample_snapshot.json
git commit -m "feat: rewrite poll for the new snapshot shape

poll now calls fetch_closed_deals + fetch_open_positions + fetch_cash_flows
per account, accumulates the three record lists, and writes a v2 Snapshot.
Drops the --source flag (MT5Source is the only source). MT5Source is now a
module-level import so test_cli can monkeypatch it with an in-test
DataSource fake. New tests/fixtures/sample_snapshot.json is the canonical
example of the v2 schema and seeds the cli fake."
```

---

## Task 5: Delete dead modules and fixtures

**Files:**
- Delete: `src/mt5_pnl_exporter/aggregate.py`
- Delete: `src/mt5_pnl_exporter/sources/fixture.py`
- Delete: `tests/test_aggregate.py`
- Delete: `tests/fixtures/sample_deals.json`

- [ ] **Step 1: Confirm no remaining references**

Run:
```bash
cd /Users/tane/Code/mt5-pnl-exporter
grep -rn "from mt5_pnl_exporter import aggregate\|mt5_pnl_exporter.aggregate\|deals_to_daily\|FixtureSource\|sources.fixture\|sample_deals" src/ tests/ docs/ README.md CLAUDE.md 2>/dev/null
```
Expected: no output (or only matches in `docs/superpowers/` which is historical and fine to leave).

If any production code or active test references appear, stop and fix them before deleting.

- [ ] **Step 2: Delete the files**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git rm src/mt5_pnl_exporter/aggregate.py
git rm src/mt5_pnl_exporter/sources/fixture.py
git rm tests/test_aggregate.py
git rm tests/fixtures/sample_deals.json
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass; coverage report appears at the end.

- [ ] **Step 4: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git commit -m "chore: drop aggregate.py, FixtureSource, and old fixtures

aggregate.deals_to_daily has no caller in the v2 schema. FixtureSource
served the --source fixture runtime selector which is gone. Smoke
fixtures now live as tests/fixtures/sample_snapshot.json, loaded
directly by tests."
```

---

## Task 6: Light docs touch — README + CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

Only the changes that fall out of cycle 1's code changes. The full reframe + threat model is cycle 3.

- [ ] **Step 1: Update CLAUDE.md**

Apply these edits to `/Users/tane/Code/mt5-pnl-exporter/CLAUDE.md`:

a) Replace the `Commands` block's poll line:

Find:
```
uv run mt5-pnl-exporter poll --source fixture   # smoke-test without creds
```
Replace with:
```
uv run mt5-pnl-exporter poll                   # run a real poll (Windows + creds)
```

b) Replace the `Architecture` section bullets for `sources/` and `aggregate.py`:

Find:
```
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only); `FixtureSource` (local JSON for dev / tests).
- `aggregate.py` — `deals_to_daily()` runs inside `poll`.
```
Replace with:
```
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only) is the sole implementation.
```

c) Replace the `snapshot.py` and `config.py` architecture bullets:

Find:
```
- `snapshot.py` — typed pydantic models + atomic `write` (temp file + `replace`). `read()` rejects mismatched `SCHEMA_VERSION`.
- `config.py` — pydantic models + YAML loader. Poll-side only — no query-side config (`account_groups`, `staleness_warn_hours`) here.
```
Replace with:
```
- `snapshot.py` — typed pydantic models for `AccountSnapshot`, `ClosedDeal`, `OpenPosition`, `CashFlow` + atomic `write` (temp file + `replace`). `read()` rejects mismatched `SCHEMA_VERSION` (currently `2`). One record per closed deal, position, and cash flow — no pre-aggregation.
- `config.py` — pydantic models + YAML loader. Flat shape: `snapshot_path`, `terminal_path`, `accounts` at the top level.
```

d) Update the Gotchas:

Find:
```
- **Deal filtering**: only `DEAL_ENTRY_OUT`/`INOUT` closing deals count; `DEAL_TYPE_BALANCE` is excluded. Net P&L = profit+swap+commission+fee; net of exactly 0 counts as a win.
```
Replace with:
```
- **Deal classification**: `MT5Source.fetch_closed_deals` keeps only `DEAL_ENTRY_OUT`/`INOUT` records with non-balance-family types. `fetch_cash_flows` keeps only balance-family types (`BALANCE`, `CREDIT`, `CHARGE`, `CORRECTION`, `BONUS`, `COMMISSION`). `_get_history_raw` memoises `history_deals_get` per `(login, date_from, date_to)` so the two fetchers share one round-trip to MT5.
```

Find:
```
- **`SCHEMA_VERSION` is still a plain integer** in 0.x. Major.minor versioning ships in Phase 1b.
```
Replace with:
```
- **`SCHEMA_VERSION` is `2`** (plain integer). Major.minor versioning lands in Phase 1b cycle 4.
```

e) Update the Conventions:

Find:
```
- Tests target `aggregate.py` and `snapshot.py`. Use `FixtureSource` instead of mocking MT5.
```
Replace with:
```
- Tests target `snapshot.py` (round-trip) and `sources/mt5.py` (call-shape + field-copy fidelity via a fake MetaTrader5 module). End-to-end CLI tests inject an in-test fake `DataSource` in place of `MT5Source`.
```

- [ ] **Step 2: Update README.md**

The README's contents vary; before editing, read it:

```bash
cat /Users/tane/Code/mt5-pnl-exporter/README.md
```

Apply these edits where the patterns appear:

a) Any reference to `--source fixture` in install/usage examples — remove the line, or replace it with the simple `uv run mt5-pnl-exporter poll` invocation.
b) Any mention of `DailyRow` or "daily aggregated" snapshot shape — replace with a brief description: "one record per closed deal, open position, and balance-family deal (cash flow)".
c) Add a new short section titled `## Snapshot size` immediately after the schema description (or at the end of the file if no schema section exists), with this text:

```markdown
## Snapshot size

The snapshot stores one record per closed deal, so it grows with trading
volume. Rough sizing: ~350 bytes per closed-deal record. Ten accounts
with two years of 50-deals-per-day-per-account history is around 85 MB;
busier setups (200 deals/day) reach ~350 MB. Local reads and writes are
fast at these sizes — the only operational concern is transport over a
sync service (Dropbox, Syncthing) re-syncing the whole file each poll.
Mitigation lands in Phase 1b cycle 2, which adds gzip-before-encryption.
```

If the README already has the new shape described accurately (e.g. it was rewritten earlier), skip (a) and (b) and only add (c).

- [ ] **Step 3: Render-check the README**

Run:
```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh api -X POST /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter -F text=@README.md > /tmp/readme-rendered.html
echo "rendered $(wc -c </tmp/readme-rendered.html) bytes"
grep -c '<h[1-6]' /tmp/readme-rendered.html
```
Expected: a positive byte count and at least one heading. If the render command errors, report the error and stop.

- [ ] **Step 4: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add CLAUDE.md README.md
git commit -m "docs: align CLAUDE.md + README with the v2 snapshot shape

Light cycle-1 touch only — describes the new record types, the flat
config, and the snapshot-size implications. Full reframe (Windows host
framing, threat model, keychain audit) is cycle 3."
```

---

## Task 7: Final verification + push

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite with coverage**

Run: `uv run pytest`
Expected: all pass; coverage report shows ≥95% (the project's configured threshold). If coverage dips below 95%, identify the uncovered lines from the report and add targeted tests before continuing.

- [ ] **Step 2: Lint**

Run: `uv run ruff check src/ tests/`
Expected: no errors.

- [ ] **Step 3: Format check**

Run: `uv run ruff format --check src/ tests/`
Expected: no diff. If diffs are reported, run `uv run ruff format src/ tests/` and commit the formatting changes as `style: ruff format`.

- [ ] **Step 4: Type check**

Run: `uv run mypy src/mt5_pnl_exporter`
Expected: no errors.

- [ ] **Step 5: Verify the schema file is up to date**

Run: `uv run mt5-pnl-exporter schema` then `git diff --stat schema/snapshot.schema.json`
Expected: no diff (schema was regenerated in Task 1).

- [ ] **Step 6: Push the branch and open a PR**

Cycle 1 work lives on `phase-1b-cycle-1`. Push the branch and open a draft PR for review; do NOT merge or push to `main`.

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git status
git log --oneline main..HEAD
git push -u origin phase-1b-cycle-1
gh pr create --draft --base main --head phase-1b-cycle-1 \
  --title "Phase 1b cycle 1: snapshot redesign + cascades" \
  --body "$(cat <<'EOF'
## Summary
- Replaces `DailyRow` with raw `ClosedDeal` / `OpenPosition` / `CashFlow` records (schema v2).
- `DataSource` protocol grows to three fetchers; `MT5Source` memoises `history_deals_get`.
- Drops `aggregate.py`, `FixtureSource`, the `--source` flag, and the `poll:` config wrapper.
- Tests pivot to snapshot round-trip + source field-copy fidelity; new `tests/fixtures/sample_snapshot.json`.

See [`docs/superpowers/specs/2026-06-01-phase-1b-cycle-1-design.md`](docs/superpowers/specs/2026-06-01-phase-1b-cycle-1-design.md)
and [`docs/superpowers/plans/2026-06-01-phase-1b-cycle-1.md`](docs/superpowers/plans/2026-06-01-phase-1b-cycle-1.md).

## Test plan
- [ ] `uv run pytest` passes with coverage ≥ 95%
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run ruff format --check src/ tests/` clean
- [ ] `uv run mypy src/mt5_pnl_exporter` clean
- [ ] `schema/snapshot.schema.json` regenerated and committed
EOF
)"
```
Expected: `git status` reports a clean tree; `git log` shows the cycle-1 commits; `git push` succeeds; `gh pr create` returns a PR URL. Report the URL back to the user.

---

## Self-Review (completed before saving)

**Spec coverage:**
- Schema redesign (item 1) → Task 1.
- MT5 source extensions (item 2) → Task 2.
- Drop `FixtureSource` runtime (item 3) → Tasks 4 (cli stops using it) and 5 (delete).
- Tests restructured (item 4) → Tasks 1, 2, 3, 4 each rewrite their domain's tests.
- Config flatten (item 5) → Task 3.
- Light docs touch (per spec's "Docs" subsection) → Task 6.
- Forward-looking gzip note → Task 6 README addition.

**Placeholder scan:** no TBDs, no "implement later", no "similar to Task N", no naked "add tests". Each step contains the actual content to write or the exact command to run.

**Type consistency:** `ClosedDeal`/`OpenPosition`/`CashFlow` field names match across snapshot.py, mt5.py, test_mt5_source.py, sample_snapshot.json, and the test factories. `_history_cache` referenced in tests matches the attribute name on `MT5Source`. `fetch_closed_deals`/`fetch_open_positions`/`fetch_cash_flows` signatures match between the protocol, implementation, fake, and cli call sites.
