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
        ticket=0,
        order=0,
        position_id=0,
        time=0,
        time_msc=0,
        type=0,
        entry=0,
        reason=0,
        magic=0,
        volume=0.0,
        price=0.0,
        profit=0.0,
        swap=0.0,
        commission=0.0,
        fee=0.0,
        symbol="",
        comment="",
        external_id="",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_position(**kwargs: Any) -> types.SimpleNamespace:
    """Build a fake MT5 TradePosition-shaped record with default zero/empty fields."""
    defaults = dict(
        ticket=0,
        identifier=0,
        time=0,
        time_msc=0,
        time_update=0,
        time_update_msc=0,
        type=0,
        reason=0,
        magic=0,
        volume=0.0,
        price_open=0.0,
        price_current=0.0,
        sl=0.0,
        tp=0.0,
        profit=0.0,
        swap=0.0,
        symbol="",
        comment="",
        external_id="",
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
