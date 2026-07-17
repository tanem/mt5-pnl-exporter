# Execution-quality capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opening-deal, order-history, and per-symbol metadata to the snapshot (schema 1.0 → 1.1) so per-trade slippage can be computed across accounts running the same EA.

**Architecture:** Additive schema bump. Three new snapshot lists — `entry_deals` (reusing the existing `ClosedDeal` model, filtered to `DEAL_ENTRY_IN`), `orders` (a new `Order` model from `history_orders_get`, all states), and `symbols` (a minimal `SymbolInfo` model from `symbol_info`). New fields default to empty lists and `schema_version` accepts both `"1.0"` and `"1.1"`, so a 1.0 reader-written snapshot still validates. Derived values (slippage-in-points) stay a consumer concern.

**Tech Stack:** Python 3.12, pydantic v2, Typer, the `MetaTrader5` package (deferred import, Windows only), pytest with an in-memory fake `MetaTrader5` module.

## Global Constraints

- Python 3.12+; `from __future__ import annotations` at the top of every module.
- British/Commonwealth English in comments and docs (realise, behaviour, colour). No hyperbole or marketing language.
- Never import `MetaTrader5` at module level — it stays deferred inside `MT5Source`.
- Enum-ish MT5 fields (`type`, `entry`, `state`, `reason`, …) are kept as **raw MT5 integers**; no string translation.
- One record per MT5 deal/order — no pre-aggregation, no derived values baked into the snapshot.
- `SCHEMA_VERSION` is a major.minor string; this change moves it `"1.0"` → `"1.1"` (`_MINOR` 0 → 1). Additive fields bump the minor.
- Tests must keep coverage at 100% (`uv run pytest`); the schema-staleness check (`tests/test_schema_file.py`) must stay green after regenerating `schema/snapshot.schema.json`.
- After changing commands, architecture, or a gotcha, update `CLAUDE.md` and `README.md` in the same change.
- Trading-repo privacy: no personal financial/broker/account specifics or local paths in committed artifacts; keep domain examples generic.

---

### Task 1: Snapshot models — `Order`, `SymbolInfo`, new lists, version bump

**Files:**
- Modify: `src/mt5_pnl_exporter/snapshot.py`
- Modify: `tests/test_snapshot.py`
- Regenerate: `schema/snapshot.schema.json`
- Test: `tests/test_snapshot.py`, `tests/test_schema_file.py`

**Interfaces:**
- Consumes: nothing (foundational task).
- Produces:
  - `class Order(BaseModel)` — frozen, `extra="forbid"`, fields: `account: int`, `ticket: int`, `time_setup: int`, `time_setup_msc: int`, `time_done: int`, `time_done_msc: int`, `type: int`, `state: int`, `type_filling: int`, `type_time: int`, `magic: int`, `position_id: int`, `position_by_id: int`, `reason: int`, `volume_initial: float`, `volume_current: float`, `price_open: float`, `price_current: float`, `price_stoplimit: float`, `sl: float`, `tp: float`, `symbol: str`, `comment: str`, `external_id: str`.
  - `class SymbolInfo(BaseModel)` — frozen, `extra="forbid"`, fields: `name: str`, `point: float`, `digits: int`, `trade_contract_size: float`.
  - `Snapshot` gains `entry_deals: list[ClosedDeal]`, `orders: list[Order]`, `symbols: list[SymbolInfo]`, each `Field(default_factory=list)`.
  - `SCHEMA_VERSION == "1.1"`, `_MINOR == 1`, `schema_version: Literal["1.0", "1.1"]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_snapshot.py` (near the other builders and round-trip tests):

```python
def _order(ticket: int = 1) -> "Order":
    from mt5_pnl_exporter.snapshot import Order

    return Order(
        account=1234567,
        ticket=ticket,
        time_setup=1700000000,
        time_setup_msc=1700000000123,
        time_done=1700000100,
        time_done_msc=1700000100456,
        type=0,
        state=4,
        type_filling=0,
        type_time=0,
        magic=42,
        position_id=ticket * 100,
        position_by_id=0,
        reason=3,
        volume_initial=0.10,
        volume_current=0.0,
        price_open=1.23456,
        price_current=1.23460,
        price_stoplimit=0.0,
        sl=0.0,
        tp=0.0,
        symbol="EURUSD",
        comment="",
        external_id="",
    )


def _symbol_info(name: str = "EURUSD") -> "SymbolInfo":
    from mt5_pnl_exporter.snapshot import SymbolInfo

    return SymbolInfo(name=name, point=0.00001, digits=5, trade_contract_size=100000.0)


def test_roundtrip_entry_deals_orders_symbols(tmp_path):
    from mt5_pnl_exporter.snapshot import SCHEMA_VERSION, Snapshot

    snap_path = tmp_path / "snapshot.json.gz.age"
    snap = Snapshot(
        schema_version=SCHEMA_VERSION,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[_closed_deal()],
        open_positions=[_open_position()],
        cash_flows=[_cash_flow()],
        entry_deals=[_closed_deal(ticket=2)],
        orders=[_order(ticket=3)],
        symbols=[_symbol_info()],
    )
    write(snap_path, snap, PASSPHRASE)
    result = read(snap_path, PASSPHRASE)
    assert result.schema_version == "1.1"
    assert [d.ticket for d in result.entry_deals] == [2]
    assert [o.ticket for o in result.orders] == [3]
    assert result.orders[0].price_open == 1.23456
    assert result.orders[0].state == 4
    assert [s.name for s in result.symbols] == ["EURUSD"]
    assert result.symbols[0].point == 0.00001


def test_read_accepts_legacy_1_0_snapshot_without_new_fields(tmp_path):
    """A 1.0 payload missing entry_deals/orders/symbols reads with empty defaults."""
    import gzip
    import json

    import pyrage

    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "1.0",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    snap_path.write_bytes(pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE))
    result = read(snap_path, PASSPHRASE)
    assert result.schema_version == "1.0"
    assert result.entry_deals == []
    assert result.orders == []
    assert result.symbols == []
```

Replace the existing `test_read_rejects_future_minor` body so it targets a
genuinely-future minor (1.2, since 1.1 is now accepted):

```python
def test_read_rejects_future_minor(tmp_path):
    """A newer minor (1.2) is still rejected by a 1.1 reader."""
    import gzip
    import json

    import pyrage

    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "1.2",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    snap_path.write_bytes(pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE))
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_snapshot.py -k "entry_deals_orders_symbols or legacy_1_0 or future_minor" -v`
Expected: FAIL — `Order`/`SymbolInfo` not importable; `SCHEMA_VERSION` still `"1.0"`; 1.2 currently rejected but 1.1 test path not yet present.

- [ ] **Step 3: Implement the model changes**

In `src/mt5_pnl_exporter/snapshot.py`:

Change the import line to add `Field`:

```python
from pydantic import BaseModel, ConfigDict, Field
```

Bump the version constants:

```python
SCHEMA_VERSION = "1.1"
_MAJOR = 1
_MINOR = 1
```

Add the two new models after `CashFlow` (before `Snapshot`):

```python
class Order(BaseModel):
    """One order — every field MT5's TradeOrder emits, plus `account`.

    Orders carry the requested price (`price_open`), the server-side setup and
    done times (for latency analysis), and `state` (filled/cancelled/rejected).
    All orders in the window are emitted, every state — not filtered to filled.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    account: int  # login — added by the exporter; MT5 orders don't carry it
    ticket: int
    time_setup: int  # Unix seconds — order reached the server
    time_setup_msc: int  # Unix milliseconds
    time_done: int  # Unix seconds — filled or cancelled
    time_done_msc: int
    type: int  # mt5 ORDER_TYPE_* (raw integer)
    state: int  # mt5 ORDER_STATE_* (raw integer)
    type_filling: int  # mt5 ORDER_FILLING_*
    type_time: int  # mt5 ORDER_TIME_*
    magic: int
    position_id: int
    position_by_id: int
    reason: int  # mt5 ORDER_REASON_*
    volume_initial: float
    volume_current: float
    price_open: float  # requested price
    price_current: float
    price_stoplimit: float
    sl: float
    tp: float
    symbol: str
    comment: str
    external_id: str


class SymbolInfo(BaseModel):
    """Minimal per-symbol metadata for converting price gaps to points.

    Only the fields that are stable at export time — the rest of MT5's
    symbol_info is live market state (bid/ask/spread) meaningless in a snapshot.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    point: float
    digits: int
    trade_contract_size: float
```

Update the `Snapshot` model:

```python
class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["1.0", "1.1"]
    generated_at: str
    accounts: list[AccountSnapshot]
    closed_deals: list[ClosedDeal]
    open_positions: list[OpenPosition]
    cash_flows: list[CashFlow]
    entry_deals: list[ClosedDeal] = Field(default_factory=list)
    orders: list[Order] = Field(default_factory=list)
    symbols: list[SymbolInfo] = Field(default_factory=list)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_snapshot.py -v`
Expected: PASS (all snapshot tests, including the three new/updated ones).

- [ ] **Step 5: Regenerate the schema**

Run: `uv run mt5-pnl-exporter schema`
Then: `uv run pytest tests/test_schema_file.py -v`
Expected: `schema/snapshot.schema.json` now contains `Order`, `SymbolInfo`, `entry_deals`, `orders`, `symbols`, and `schema_version` enum `["1.0", "1.1"]`; the staleness test passes.

- [ ] **Step 6: Commit**

```bash
git add src/mt5_pnl_exporter/snapshot.py tests/test_snapshot.py schema/snapshot.schema.json
git commit -m "feat: add Order/SymbolInfo models and 1.1 snapshot fields"
```

---

### Task 2: `MT5Source.fetch_entry_deals` — opening deals

**Files:**
- Modify: `src/mt5_pnl_exporter/sources/base.py`
- Modify: `src/mt5_pnl_exporter/sources/mt5.py`
- Test: `tests/test_mt5_source.py`

**Interfaces:**
- Consumes: `ClosedDeal` (Task 1 leaves it unchanged); the existing `_get_history_raw` memoised fetch.
- Produces: `MT5Source.fetch_entry_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]`; `DEAL_ENTRY_IN = 0` in `base.py`; `DataSource.fetch_entry_deals` protocol method.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_mt5_source.py`:

```python
def test_fetch_entry_deals_keeps_only_opening_non_balance():
    """Only DEAL_ENTRY_IN, non-balance deals land in entry_deals."""
    from mt5_pnl_exporter.sources.base import (
        DEAL_ENTRY_IN,
        DEAL_ENTRY_OUT,
        DEAL_TYPE_BALANCE,
    )

    DEAL_TYPE_BUY = 0
    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_IN, price=1.2345),  # kept
        _make_deal(ticket=2, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT),  # dropped — closing
        _make_deal(ticket=3, type=DEAL_TYPE_BALANCE, entry=DEAL_ENTRY_IN),  # dropped — balance
    ]
    _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_entry_deals(514248, 0, 1)
        assert [d.ticket for d in result] == [1]
        assert result[0].account == 514248
        assert result[0].price == 1.2345
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_entry_deals_shares_history_round_trip():
    """fetch_closed_deals then fetch_entry_deals for one window hits MT5 once."""
    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_IN),
        _make_deal(ticket=2, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT),
    ]
    fake = _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        src.fetch_closed_deals(514248, 0, 1)
        src.fetch_entry_deals(514248, 0, 1)
        get_calls = [c for c in fake.calls if c[0] == "history_deals_get"]
        assert len(get_calls) == 1
    finally:
        sys.modules.pop("MetaTrader5", None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mt5_source.py -k entry_deals -v`
Expected: FAIL — `DEAL_ENTRY_IN` not exported from `base.py`; `fetch_entry_deals` not defined.

- [ ] **Step 3: Implement**

In `src/mt5_pnl_exporter/sources/base.py`, add the constant beside the other entry constants (after the comment block ending at `DEAL_ENTRY_OUT_BY = 3`):

```python
DEAL_ENTRY_IN = 0
```

Add the protocol method inside `class DataSource` (after `fetch_closed_deals`):

```python
    def fetch_entry_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]: ...
```

In `src/mt5_pnl_exporter/sources/mt5.py`, add `DEAL_ENTRY_IN` to the import from `sources.base`:

```python
from mt5_pnl_exporter.sources.base import (
    BALANCE_FAMILY_TYPES,
    DEAL_ENTRY_IN,
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_ENTRY_OUT_BY,
    AccountInfo,
)
```

Add the method after `fetch_closed_deals`:

```python
    def fetch_entry_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]:
        raw = self._get_history_raw(login, date_from, date_to)
        out: list[ClosedDeal] = []
        for d in raw:
            if d.type in BALANCE_FAMILY_TYPES:
                continue
            if d.entry != DEAL_ENTRY_IN:
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mt5_source.py -k entry_deals -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/sources/base.py src/mt5_pnl_exporter/sources/mt5.py tests/test_mt5_source.py
git commit -m "feat: fetch entry (opening) deals from MT5 history"
```

---

### Task 3: `MT5Source.fetch_orders` — order history with its own cache

**Files:**
- Modify: `src/mt5_pnl_exporter/sources/base.py`
- Modify: `src/mt5_pnl_exporter/sources/mt5.py`
- Test: `tests/test_mt5_source.py`

**Interfaces:**
- Consumes: `Order` (Task 1); `_connect`, `_wait_history_synced` (existing).
- Produces: `MT5Source.fetch_orders(self, login: int, date_from: int, date_to: int) -> list[Order]`; a `_orders_cache` cleared in `shutdown()`; `DataSource.fetch_orders` protocol method; a `_make_order` test helper.

- [ ] **Step 1: Write the failing tests**

First, extend the fake module. In `_install_fake_mt5`, add an `orders` parameter and a `history_orders_get` function, registered like the others. Change the signature and body:

```python
def _install_fake_mt5(
    login_ok: bool = True,
    init_ok: bool = True,
    history_total_values: list[int] | None = None,
    history_deals: list | None = None,
    positions: list | None = None,
    orders: list | None = None,
) -> types.ModuleType:
```

Inside, alongside `history_deals_get`:

```python
    def history_orders_get(*args: Any, **kwargs: Any) -> list:
        fake.calls.append(("history_orders_get", args, kwargs))  # type: ignore[attr-defined]
        return list(orders or [])
```

And register it beside the other assignments:

```python
    fake.history_orders_get = history_orders_get  # type: ignore[attr-defined]
```

Add an order builder beside `_make_deal`:

```python
def _make_order(**kwargs: Any) -> types.SimpleNamespace:
    """Build a fake MT5 TradeOrder-shaped record with default zero/empty fields."""
    defaults = dict(
        ticket=0,
        time_setup=0,
        time_setup_msc=0,
        time_done=0,
        time_done_msc=0,
        type=0,
        state=0,
        type_filling=0,
        type_time=0,
        magic=0,
        position_id=0,
        position_by_id=0,
        reason=0,
        volume_initial=0.0,
        volume_current=0.0,
        price_open=0.0,
        price_current=0.0,
        price_stoplimit=0.0,
        sl=0.0,
        tp=0.0,
        symbol="",
        comment="",
        external_id="",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)
```

Then the tests:

```python
def test_fetch_orders_copies_every_field():
    """All TradeOrder fields land on Order unchanged, plus account=login. All states kept."""
    order = _make_order(
        ticket=555,
        time_setup=1700000000,
        time_setup_msc=1700000000123,
        time_done=1700000100,
        time_done_msc=1700000100456,
        type=0,
        state=4,
        type_filling=1,
        type_time=0,
        magic=42,
        position_id=987654,
        position_by_id=0,
        reason=3,
        volume_initial=0.10,
        volume_current=0.0,
        price_open=1.23456,
        price_current=1.23460,
        price_stoplimit=0.0,
        sl=1.2300,
        tp=1.2400,
        symbol="EURUSD",
        comment="req",
        external_id="ext-ord-1",
    )
    _install_fake_mt5(orders=[order])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_orders(514248, 0, 1)
        assert len(result) == 1
        o = result[0]
        assert o.account == 514248
        assert o.ticket == 555
        assert o.time_setup_msc == 1700000000123
        assert o.time_done_msc == 1700000100456
        assert o.state == 4
        assert o.type_filling == 1
        assert o.position_id == 987654
        assert o.volume_initial == 0.10
        assert o.price_open == 1.23456
        assert o.price_current == 1.23460
        assert o.sl == 1.2300
        assert o.tp == 1.2400
        assert o.symbol == "EURUSD"
        assert o.comment == "req"
        assert o.external_id == "ext-ord-1"
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_orders_returns_empty_when_none_and_no_error():
    fake = _install_fake_mt5()
    fake.history_orders_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (1, "ERR_SUCCESS")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        assert src.fetch_orders(514248, 0, 1) == []
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_orders_raises_when_none_and_mt5_error():
    fake = _install_fake_mt5()
    fake.history_orders_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (-10004, "Invalid timeout")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="history_orders_get failed"):
            src.fetch_orders(514248, 0, 1)
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_orders_cached_per_window():
    """Two fetch_orders calls for one window hit MT5 once; shutdown clears the cache."""
    fake = _install_fake_mt5(orders=[_make_order(ticket=1)])
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        src.fetch_orders(514248, 0, 1)
        src.fetch_orders(514248, 0, 1)
        get_calls = [c for c in fake.calls if c[0] == "history_orders_get"]
        assert len(get_calls) == 1
        assert src._orders_cache != {}
        src.shutdown()
        assert src._orders_cache == {}
    finally:
        sys.modules.pop("MetaTrader5", None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mt5_source.py -k fetch_orders -v`
Expected: FAIL — `fetch_orders` and `_orders_cache` not defined.

- [ ] **Step 3: Implement**

In `src/mt5_pnl_exporter/sources/base.py`, add to `from mt5_pnl_exporter.snapshot import ...`:

```python
from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition, Order
```

Add the protocol method inside `class DataSource` (after `fetch_cash_flows`):

```python
    def fetch_orders(self, login: int, date_from: int, date_to: int) -> list[Order]: ...
```

In `src/mt5_pnl_exporter/sources/mt5.py`:

Import `Order`:

```python
from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition, Order
```

In `__init__`, after the `self._history_cache` line, add:

```python
        # Order history cached per (login, date_from, date_to), same as deals.
        self._orders_cache: dict[tuple[int, int, int], list[Any]] = {}
```

Add a raw-orders fetch after `_get_history_raw`:

```python
    def _get_orders_raw(self, login: int, date_from: int, date_to: int) -> list[Any]:
        """Return the raw history_orders_get result for the window, cached."""
        key = (login, date_from, date_to)
        if key in self._orders_cache:
            return self._orders_cache[key]

        self._connect(login)
        dt_from = datetime.datetime.fromtimestamp(date_from, tz=datetime.UTC)
        dt_to = datetime.datetime.fromtimestamp(date_to, tz=datetime.UTC)
        self._wait_history_synced(login, dt_from, dt_to)
        raw = self._mt5.history_orders_get(dt_from, dt_to)
        if raw is None:
            code, msg = self._mt5.last_error()
            if code != 1:  # 1 = ERR_SUCCESS / no orders in range
                raise RuntimeError(f"history_orders_get failed for {login}: ({code}, {msg!r})")
            raw = []
        result = list(raw)
        self._orders_cache[key] = result
        return result

    def fetch_orders(self, login: int, date_from: int, date_to: int) -> list[Order]:
        raw = self._get_orders_raw(login, date_from, date_to)
        out: list[Order] = []
        for o in raw:
            out.append(
                Order(
                    account=login,
                    ticket=int(o.ticket),
                    time_setup=int(o.time_setup),
                    time_setup_msc=int(o.time_setup_msc),
                    time_done=int(o.time_done),
                    time_done_msc=int(o.time_done_msc),
                    type=int(o.type),
                    state=int(o.state),
                    type_filling=int(o.type_filling),
                    type_time=int(o.type_time),
                    magic=int(o.magic),
                    position_id=int(o.position_id),
                    position_by_id=int(o.position_by_id),
                    reason=int(o.reason),
                    volume_initial=float(o.volume_initial),
                    volume_current=float(o.volume_current),
                    price_open=float(o.price_open),
                    price_current=float(o.price_current),
                    price_stoplimit=float(o.price_stoplimit),
                    sl=float(o.sl),
                    tp=float(o.tp),
                    symbol=str(o.symbol),
                    comment=str(o.comment),
                    external_id=str(o.external_id),
                )
            )
        return out
```

In `shutdown`, clear the new cache alongside `_history_cache`:

```python
    def shutdown(self) -> None:
        if self._initialized:
            self._mt5.shutdown()
            self._initialized = False
        self._history_cache.clear()
        self._orders_cache.clear()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mt5_source.py -k fetch_orders -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/sources/base.py src/mt5_pnl_exporter/sources/mt5.py tests/test_mt5_source.py
git commit -m "feat: fetch order history (all states) from MT5"
```

---

### Task 4: `MT5Source.fetch_symbols` — per-symbol point metadata

**Files:**
- Modify: `src/mt5_pnl_exporter/sources/base.py`
- Modify: `src/mt5_pnl_exporter/sources/mt5.py`
- Test: `tests/test_mt5_source.py`

**Interfaces:**
- Consumes: `SymbolInfo` (Task 1); `_get_history_raw` (deals), `_get_orders_raw` (Task 3).
- Produces: `MT5Source.fetch_symbols(self, login: int, date_from: int, date_to: int) -> list[SymbolInfo]`; `DataSource.fetch_symbols` protocol method; a `symbol_info` function on the fake module.

- [ ] **Step 1: Write the failing tests**

Add a `symbol_info` to the fake module. Inside `_install_fake_mt5`, define and register it (returns a per-name namespace; unknown symbols return `None`):

```python
    def symbol_info(name: str) -> Any:
        fake.calls.append(("symbol_info", (name,), {}))  # type: ignore[attr-defined]
        table = {
            "EURUSD": types.SimpleNamespace(
                point=0.00001, digits=5, trade_contract_size=100000.0
            ),
            "GBPUSD": types.SimpleNamespace(
                point=0.00001, digits=5, trade_contract_size=100000.0
            ),
        }
        return table.get(name)
```

Register beside the others:

```python
    fake.symbol_info = symbol_info  # type: ignore[attr-defined]
```

Then the tests:

```python
def test_fetch_symbols_collects_distinct_traded_symbols():
    """One SymbolInfo per distinct symbol across deals and orders; one symbol_info call each."""
    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_OUT = 1
    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, symbol="EURUSD"),
        _make_deal(ticket=2, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, symbol="EURUSD"),
    ]
    orders = [_make_order(ticket=9, symbol="GBPUSD")]
    fake = _install_fake_mt5(history_deals=deals, orders=orders)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_symbols(514248, 0, 1)
        by_name = {s.name: s for s in result}
        assert set(by_name) == {"EURUSD", "GBPUSD"}
        assert by_name["EURUSD"].point == 0.00001
        assert by_name["EURUSD"].digits == 5
        assert by_name["EURUSD"].trade_contract_size == 100000.0
        info_calls = [c for c in fake.calls if c[0] == "symbol_info"]
        assert sorted(c[1][0] for c in info_calls) == ["EURUSD", "GBPUSD"]
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_symbols_skips_empty_and_unknown_symbols():
    """Balance deals (empty symbol) and symbols MT5 can't resolve are skipped."""
    DEAL_TYPE_BUY = 0
    DEAL_ENTRY_OUT = 1
    from mt5_pnl_exporter.sources.base import DEAL_TYPE_BALANCE

    deals = [
        _make_deal(ticket=1, type=DEAL_TYPE_BALANCE, symbol=""),  # empty symbol — skipped
        _make_deal(ticket=2, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, symbol="XAUUSD"),  # unknown
        _make_deal(ticket=3, type=DEAL_TYPE_BUY, entry=DEAL_ENTRY_OUT, symbol="EURUSD"),
    ]
    _install_fake_mt5(history_deals=deals)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_symbols(514248, 0, 1)
        assert [s.name for s in result] == ["EURUSD"]
    finally:
        sys.modules.pop("MetaTrader5", None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mt5_source.py -k fetch_symbols -v`
Expected: FAIL — `fetch_symbols` not defined.

- [ ] **Step 3: Implement**

In `src/mt5_pnl_exporter/sources/base.py`, add `SymbolInfo` to the snapshot import:

```python
from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition, Order, SymbolInfo
```

Add the protocol method inside `class DataSource` (after `fetch_orders`):

```python
    def fetch_symbols(self, login: int, date_from: int, date_to: int) -> list[SymbolInfo]: ...
```

In `src/mt5_pnl_exporter/sources/mt5.py`, add `SymbolInfo` to the snapshot import:

```python
from mt5_pnl_exporter.snapshot import CashFlow, ClosedDeal, OpenPosition, Order, SymbolInfo
```

Add the method after `fetch_orders`:

```python
    def fetch_symbols(self, login: int, date_from: int, date_to: int) -> list[SymbolInfo]:
        deals = self._get_history_raw(login, date_from, date_to)
        orders = self._get_orders_raw(login, date_from, date_to)
        names: list[str] = []
        seen: set[str] = set()
        for rec in (*deals, *orders):
            name = str(rec.symbol)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        out: list[SymbolInfo] = []
        for name in names:
            info = self._mt5.symbol_info(name)
            if info is None:
                continue
            out.append(
                SymbolInfo(
                    name=name,
                    point=float(info.point),
                    digits=int(info.digits),
                    trade_contract_size=float(info.trade_contract_size),
                )
            )
        return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mt5_source.py -k fetch_symbols -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/sources/base.py src/mt5_pnl_exporter/sources/mt5.py tests/test_mt5_source.py
git commit -m "feat: fetch per-symbol point metadata for traded symbols"
```

---

### Task 5: Wire the new data into `export`

**Files:**
- Modify: `src/mt5_pnl_exporter/cli.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `MT5Source.fetch_entry_deals`, `fetch_orders`, `fetch_symbols` (Tasks 2–4); `Order`, `SymbolInfo`, `Snapshot` new fields (Task 1).
- Produces: an `export` that populates `entry_deals`, `orders`, `symbols` in the written snapshot; an updated `_FakeSource` satisfying the extended `DataSource`.

- [ ] **Step 1: Write the failing tests**

Extend `_FakeSource` in `tests/test_cli.py` — add the imports, constructor params, and three methods. Change the import block:

```python
from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Order,
    Snapshot,
    SymbolInfo,
)
```

Extend `_FakeSource.__init__` signature and body:

```python
    def __init__(
        self,
        accounts: dict[int, AccountInfo] | None = None,
        closed_deals: dict[int, list[ClosedDeal]] | None = None,
        open_positions: dict[int, list[OpenPosition]] | None = None,
        cash_flows: dict[int, list[CashFlow]] | None = None,
        entry_deals: dict[int, list[ClosedDeal]] | None = None,
        orders: dict[int, list[Order]] | None = None,
        symbols: dict[int, list[SymbolInfo]] | None = None,
        fail_logins: set[int] | None = None,
    ) -> None:
        self._accounts = accounts or {}
        self._closed = closed_deals or {}
        self._open = open_positions or {}
        self._flows = cash_flows or {}
        self._entry = entry_deals or {}
        self._orders = orders or {}
        self._symbols = symbols or {}
        self._fail = fail_logins or set()
        self.shutdown_called = False
```

Add the three fetch methods beside the existing ones:

```python
    def fetch_entry_deals(self, login: int, _from: int, _to: int) -> list[ClosedDeal]:
        self._check(login)
        return self._entry.get(login, [])

    def fetch_orders(self, login: int, _from: int, _to: int) -> list[Order]:
        self._check(login)
        return self._orders.get(login, [])

    def fetch_symbols(self, login: int, _from: int, _to: int) -> list[SymbolInfo]:
        self._check(login)
        return self._symbols.get(login, [])
```

Update the existing happy-path assertion in
`test_export_writes_snapshot_with_all_record_types` — the exporter now stamps
1.1:

```python
    assert snap.schema_version == "1.1"
```

Add a focused new test:

```python
def test_export_includes_entry_deals_orders_symbols(tmp_path, install_fake):
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o600)

    entry = ClosedDeal(
        account=1234567, ticket=10, order=100, position_id=1000, time=1700000000,
        time_msc=1700000000000, type=0, entry=0, reason=0, magic=0, volume=0.1,
        price=1.2345, profit=0.0, swap=0.0, commission=0.0, fee=0.0, symbol="EURUSD",
        comment="", external_id="",
    )
    order = Order(
        account=1234567, ticket=100, time_setup=1700000000, time_setup_msc=1700000000000,
        time_done=1700000100, time_done_msc=1700000100000, type=0, state=4, type_filling=0,
        type_time=0, magic=0, position_id=1000, position_by_id=0, reason=3,
        volume_initial=0.1, volume_current=0.0, price_open=1.2344, price_current=1.2345,
        price_stoplimit=0.0, sl=0.0, tp=0.0, symbol="EURUSD", comment="", external_id="",
    )
    sym = SymbolInfo(name="EURUSD", point=0.00001, digits=5, trade_contract_size=100000.0)

    fake = _FakeSource(
        accounts={1234567: AccountInfo(
            login=1234567, label="Trend EA", currency="USD", balance=1000.0, equity=1000.0,
        )},
        entry_deals={1234567: [entry]},
        orders={1234567: [order]},
        symbols={1234567: [sym]},
    )
    install_fake(fake)

    result = runner.invoke(app, ["export", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.output

    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    assert [d.ticket for d in snap.entry_deals] == [10]
    assert [o.ticket for o in snap.orders] == [100]
    assert snap.orders[0].price_open == 1.2344
    assert [s.name for s in snap.symbols] == ["EURUSD"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -k "all_record_types or entry_deals_orders_symbols" -v`
Expected: FAIL — `export` doesn't call the new fetchers; snapshot stamps 1.1 but `entry_deals`/`orders`/`symbols` are empty; the schema_version assert flips.

- [ ] **Step 3: Implement the CLI wiring**

In `src/mt5_pnl_exporter/cli.py`, extend the snapshot import:

```python
from mt5_pnl_exporter.snapshot import (
    SCHEMA_VERSION,
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Order,
    Snapshot,
    SymbolInfo,
)
```

Add the accumulators beside the existing ones (after `cash_flows_out`):

```python
    entry_deals_out: list[ClosedDeal] = []
    orders_out: list[Order] = []
    symbols_by_name: dict[str, SymbolInfo] = {}
```

Inside the per-account `try`, after `positions = src.fetch_open_positions(acct.login)`:

```python
            entry = src.fetch_entry_deals(acct.login, epoch_from, epoch_to)
            orders = src.fetch_orders(acct.login, epoch_from, epoch_to)
            symbols = src.fetch_symbols(acct.login, epoch_from, epoch_to)
```

After `open_positions_out.extend(positions)`:

```python
            entry_deals_out.extend(entry)
            orders_out.extend(orders)
            for sym in symbols:
                symbols_by_name[sym.name] = sym
```

In the `Snapshot(...)` construction, add the three fields:

```python
        snap = Snapshot(
            schema_version=SCHEMA_VERSION,
            generated_at=now.isoformat().replace("+00:00", "Z"),
            accounts=accounts_out,
            closed_deals=closed_deals_out,
            open_positions=open_positions_out,
            cash_flows=cash_flows_out,
            entry_deals=entry_deals_out,
            orders=orders_out,
            symbols=list(symbols_by_name.values()),
        )
```

Optionally extend the per-account log line to mention the new counts (keep it
one line):

```python
            log.info(
                f"[export] {acct.label} ({acct.login}): "
                f"{len(deals)} closed deals, {len(entry)} entries, "
                f"{len(orders)} orders, {len(positions)} open, "
                f"{len(flows)} cash flows  OK"
            )
```

- [ ] **Step 4: Run the full test suite to verify it passes**

Run: `uv run pytest -v`
Expected: PASS, 100% coverage.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py tests/test_cli.py
git commit -m "feat: write entry deals, orders, and symbols in export"
```

---

### Task 6: Documentation — README.md and CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: everything above (final documentation pass).
- Produces: no code; docs describing the 1.1 snapshot and the new lists.

- [ ] **Step 1: Update README.md**

Find the section that describes the snapshot contents / record types (search for
`closed_deals` and `cash_flows`). Add prose describing the three new lists:

- `entry_deals` — opening (`DEAL_ENTRY_IN`) deals, same shape as `closed_deals`; pair to a close by `position_id` to get the open fill price and time.
- `orders` — order history for the window, all states (filled, cancelled, rejected); carries `price_open` (requested price), `time_setup_msc` (order reached the server), `time_done_msc`, and `state`.
- `symbols` — per-symbol `point`, `digits`, `trade_contract_size` for the traded symbols, so a price gap can be expressed in points.

Note that slippage in points is a consumer computation:
`(order.price_open − entry_deal.price) ÷ symbol.point`, signed by direction.
State that the schema is now `1.1` and that a 1.0 reader cannot read a 1.1
snapshot (consumers must be on a 1.1-capable reader).

- [ ] **Step 2: Update CLAUDE.md**

- In the `snapshot.py` architecture bullet, note the new `Order` and `SymbolInfo` models and the `entry_deals` / `orders` / `symbols` lists, and that new fields default to empty so 1.0 snapshots still read.
- Update the deal-classification gotcha: `fetch_entry_deals` keeps `DEAL_ENTRY_IN` non-balance deals; `fetch_orders` returns all orders (every state) via `history_orders_get`, memoised per `(login, date_from, date_to)` in `_orders_cache` (cleared in `shutdown`); `fetch_symbols` collects distinct traded symbols and calls `symbol_info` per name.
- Update the `SCHEMA_VERSION` gotcha to `"1.1"`, and note `read()` accepts `1.0` and `1.1`.

- [ ] **Step 3: Verify the docs build/read and run the suite once more**

Run: `uv run pytest && uv run ruff check src/ tests/ && uv run mypy src/mt5_pnl_exporter`
Expected: all pass; docs are prose-only so nothing to execute.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: describe 1.1 snapshot — entry deals, orders, symbols"
```

---

## Verification (whole feature)

- `uv run pytest` — all tests pass; coverage 100%.
- `uv run ruff check src/ tests/` and `uv run mypy src/mt5_pnl_exporter` — clean.
- `uv run mt5-pnl-exporter schema` — no diff after commit (`test_schema_file.py` green).
- Manual narrative (Windows host, two live accounts on the same EA): run
  `export`, decrypt the snapshot, and for a matched trade compute
  `(order.price_open − entry_deal.price) ÷ symbol.point` per account and
  compare — the figure that answers why the accounts fill differently.

## Self-review notes

- **Spec coverage:** `entry_deals` (Task 2), `orders` all-states + full fields (Task 3), `symbols` minimal (Task 4), CLI wiring + version bump (Tasks 1, 5), docs (Task 6), consumer-coordination note surfaced in README (Task 6). The `mt5-pnl-cli` bump stays out of scope per the spec.
- **Back-compat:** new `Snapshot` fields default to empty and `schema_version` accepts `"1.0"`/`"1.1"`, so a 1.0 payload validates — covered by `test_read_accepts_legacy_1_0_snapshot_without_new_fields` (Task 1).
- **Order field set:** confirm against the installed `MetaTrader5` `TradeOrder` on the Windows host during Task 3; if that build exposes fields not listed here, add them to the `Order` model and the `_make_order` fake in the same task, then regenerate the schema.
