"""Tests for MT5Source — the live data backend.

CLAUDE.md prefers FixtureSource over mocking MT5, but the bugs fixed in
e233fc9 and subsequent commits were specifically in the shape of the
mt5.initialize() and mt5.login() calls — exactly the kind of issue
FixtureSource can't catch. A minimal in-memory shim for the MetaTrader5
module is justified here, scoped to call-signature contracts.
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
) -> types.ModuleType:
    """Register a fake MetaTrader5 module so MT5Source can import it.

    The shim records every call as a (name, args, kwargs) tuple.
    history_total_values controls the sequence returned by history_deals_total();
    defaults to always returning 0 (immediately stable, good for non-sync tests).
    """
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
        return []

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
    fake.account_info = account_info  # type: ignore[attr-defined]

    sys.modules["MetaTrader5"] = fake
    return fake


@pytest.fixture
def fake_mt5():
    fake = _install_fake_mt5()
    yield fake
    sys.modules.pop("MetaTrader5", None)


# ── initialize() call shape ───────────────────────────────────────────────────


def test_initialize_passes_credentials(fake_mt5):
    """First call must pass login/password/server to initialize(), not just path.

    This is the fix for (-6, 'Terminal: Authorization failed'): calling
    mt5.initialize(path) with no creds fails on a fresh terminal because
    there is no saved session to fall back on.
    """
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

    assert len(inits) == 1, "initialize() must only be called once"
    assert len(logins) == 1
    assert logins[0][1] == (999999,)
    assert logins[0][2] == {"password": "inv-pw-b", "server": "BlackBull-Live"}


def test_fetch_deals_credentials_reach_mt5(fake_mt5):
    """fetch_deals() must pass server= and password= on its first (initialize) call."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.fetch_deals(514248, 0, 1)

    init_calls = [c for c in fake_mt5.calls if c[0] == "initialize"]
    assert len(init_calls) == 1
    assert init_calls[0][2]["server"] == "BlackBull-Live"
    assert init_calls[0][2]["password"] == "inv-pw"


def test_initialize_failure_surfaces_mt5_error(monkeypatch):
    """When initialize() returns False the RuntimeError must name the code."""
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
    """login() failure (on account switch) must raise with the MT5 error code."""
    _install_fake_mt5(login_ok=False)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source(
            "C:\\fake\\terminal64.exe",
            {514248: "inv-pw-a", 999999: "inv-pw-b"},
            {514248: "BlackBull-Live", 999999: "BlackBull-Live"},
        )
        src.account_info(514248)  # first call — initialize() succeeds
        with pytest.raises(RuntimeError, match=r"MT5 login failed for 999999"):
            src.account_info(999999)  # second call — login() fails
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── history sync wait ─────────────────────────────────────────────────────────


def test_history_sync_waits_for_stability(monkeypatch):
    """fetch_deals() must poll until history_deals_total stabilises before fetching."""
    # Sequence: still downloading (0,0,3,5,7) then stable at 7 three times
    totals = [0, 0, 3, 5, 7, 7, 7]
    fake = _install_fake_mt5(history_total_values=totals)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 0.0)
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        src.fetch_deals(514248, 0, 1)

        total_calls = [c for c in fake.calls if c[0] == "history_deals_total"]
        get_calls = [c for c in fake.calls if c[0] == "history_deals_get"]

        # Must have polled at least until 7,7,7 appeared (index 4,5,6 = 7 calls)
        assert len(total_calls) >= 7
        # history_deals_get must come after all the total polls
        assert get_calls, "history_deals_get must be called"
        total_idxs = [i for i, c in enumerate(fake.calls) if c[0] == "history_deals_total"]
        get_idx = next(i for i, c in enumerate(fake.calls) if c[0] == "history_deals_get")
        assert get_idx > max(total_idxs), (
            "history_deals_get must follow all history_deals_total polls"
        )
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_history_sync_zero_trades_returns_quickly(monkeypatch):
    """fetch_deals() must accept a stable-zero count without hanging."""
    fake = _install_fake_mt5()  # history_deals_total always returns 0
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 0.0)
    try:
        from mt5_pnl_exporter.sources.mt5 import _HISTORY_SYNC_STABLE_POLLS, MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_deals(514248, 0, 1)

        assert result == []
        total_calls = [c for c in fake.calls if c[0] == "history_deals_total"]
        # Should stabilise exactly at STABLE_POLLS reads (all zeros)
        assert len(total_calls) == _HISTORY_SYNC_STABLE_POLLS
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_history_sync_timeout_raises(monkeypatch):
    """fetch_deals() must raise if the count never stabilises within the cap."""
    fake = _install_fake_mt5()
    # Override history_deals_total with an ever-growing counter so it never stabilises
    counter = [0]

    def ever_growing(*args: Any, **kwargs: Any) -> int:
        counter[0] += 1
        fake.calls.append(("history_deals_total", args, kwargs))
        return counter[0]

    fake.history_deals_total = ever_growing

    # Replace the module's time reference with a fake that jumps 10 s per monotonic()
    # call so the deadline (cap = 5s, deadline = 10s) is exceeded on the second check.
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
            src.fetch_deals(514248, 0, 1)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── history_deals_get() None handling ────────────────────────────────────────


def test_fetch_deals_returns_empty_when_none_and_no_error():
    """history_deals_get() returning None with no MT5 error means empty range."""
    fake = _install_fake_mt5()
    fake.history_deals_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (1, "ERR_SUCCESS")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_deals(514248, 0, 1)
        assert result == []
    finally:
        sys.modules.pop("MetaTrader5", None)


def test_fetch_deals_raises_when_none_and_mt5_error():
    """history_deals_get() returning None with a non-success error must raise."""
    fake = _install_fake_mt5()
    fake.history_deals_get = lambda *a, **k: None  # type: ignore[attr-defined]
    fake.last_error = lambda: (-10004, "Invalid timeout")  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="history_deals_get failed"):
            src.fetch_deals(514248, 0, 1)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── deal filtering ────────────────────────────────────────────────────────────


def test_fetch_deals_filters_balance_and_non_closing():
    """Balance deals and non-closing entries must be silently dropped."""
    from mt5_pnl_exporter.sources.base import DEAL_ENTRY_OUT, DEAL_TYPE_BALANCE

    fake = _install_fake_mt5()

    class _Deal:
        def __init__(self, ticket, type_, entry, profit=0.0, swap=0.0, commission=0.0):
            self.ticket = ticket
            self.time = 0
            self.type = type_
            self.entry = entry
            self.profit = profit
            self.swap = swap
            self.commission = commission

    DEAL_TYPE_TRADE = 0  # not DEAL_TYPE_BALANCE
    DEAL_ENTRY_IN = 0  # opening entry — not DEAL_ENTRY_OUT (1) or DEAL_ENTRY_INOUT (3)

    balance_deal = _Deal(1, DEAL_TYPE_BALANCE, DEAL_ENTRY_OUT)  # dropped — balance
    entry_deal = _Deal(2, DEAL_TYPE_TRADE, DEAL_ENTRY_IN)  # dropped — opening entry, not closing
    closing_deal = _Deal(
        3, DEAL_TYPE_TRADE, DEAL_ENTRY_OUT, profit=50.0, swap=-1.0, commission=-0.5
    )

    fake.history_deals_get = lambda *a, **k: [balance_deal, entry_deal, closing_deal]  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        result = src.fetch_deals(514248, 0, 1)

        assert len(result) == 1
        assert result[0].ticket == 3
        assert result[0].profit == 50.0
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── account_info() None handling ──────────────────────────────────────────────


def test_account_info_raises_when_mt5_returns_none():
    """account_info() must raise RuntimeError when mt5.account_info() returns None."""
    fake = _install_fake_mt5()
    fake.account_info = lambda: None  # type: ignore[attr-defined]
    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with pytest.raises(RuntimeError, match="account_info\\(\\) returned None for 514248"):
            src.account_info(514248)
    finally:
        sys.modules.pop("MetaTrader5", None)


# ── shutdown() ────────────────────────────────────────────────────────────────


def test_shutdown_calls_mt5_shutdown_when_initialized(fake_mt5):
    """shutdown() must call mt5.shutdown() and clear _initialized."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.account_info(514248)  # sets _initialized = True
    assert src._initialized

    src.shutdown()

    assert not src._initialized
    shutdown_calls = [c for c in fake_mt5.calls if c[0] == "shutdown"]
    assert len(shutdown_calls) == 1


def test_shutdown_is_noop_when_not_initialized(fake_mt5):
    """shutdown() must do nothing if _initialized is False."""
    from mt5_pnl_exporter.sources.mt5 import MT5Source

    src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
    src.shutdown()  # never initialised

    shutdown_calls = [c for c in fake_mt5.calls if c[0] == "shutdown"]
    assert shutdown_calls == []


# ── slow-sync debug log ───────────────────────────────────────────────────────


def test_history_sync_slow_log_is_emitted(monkeypatch, caplog):
    """The slow-sync debug log must fire once elapsed >= 5 s worth of polls."""
    import logging

    # Values: fluctuating counts so it never stabilises quickly.
    # We need enough polls that (len(counts)-1) * POLL_S >= 5.
    # With POLL_S patched to 1.0 and counts never stable, we need 6+ polls.
    # Provide an alternating sequence long enough to trigger the log, then stabilise.
    totals = [1, 2, 1, 2, 1, 2, 3, 3, 3]
    _install_fake_mt5(history_total_values=totals)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5._HISTORY_SYNC_POLL_S", 1.0)

    # Patch time.monotonic() so the deadline never fires, and time.sleep() is instant.
    import types as _types

    mono_val = [0.0]

    def fake_monotonic() -> float:
        return mono_val[0]  # stays well below deadline

    fake_time = _types.SimpleNamespace(monotonic=fake_monotonic, sleep=lambda s: None)
    monkeypatch.setattr("mt5_pnl_exporter.sources.mt5.time", fake_time)

    try:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        src = MT5Source("C:\\fake\\terminal64.exe", {514248: "inv-pw"}, {514248: "BlackBull-Live"})
        with caplog.at_level(logging.DEBUG, logger="mt5_pnl_exporter.sources.mt5"):
            src.fetch_deals(514248, 0, 1)

        assert any(
            "history sync" in r.message and "still in progress" in r.message for r in caplog.records
        )
    finally:
        sys.modules.pop("MetaTrader5", None)
