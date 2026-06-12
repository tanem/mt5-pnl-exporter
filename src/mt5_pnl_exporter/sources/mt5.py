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
    DEAL_ENTRY_OUT_BY,
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

    def _get_history_raw(self, login: int, date_from: int, date_to: int) -> list[Any]:
        """Return the raw history_deals_get result for the window, cached."""
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
                raise RuntimeError(f"history_deals_get failed for {login}: ({code}, {msg!r})")
            raw = []
        result = list(raw)
        self._history_cache[key] = result
        return result

    def fetch_closed_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]:
        raw = self._get_history_raw(login, date_from, date_to)
        out: list[ClosedDeal] = []
        for d in raw:
            if d.type in BALANCE_FAMILY_TYPES:
                continue
            if d.entry not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT, DEAL_ENTRY_OUT_BY):
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

    def fetch_cash_flows(self, login: int, date_from: int, date_to: int) -> list[CashFlow]:
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

    def fetch_account_info(self, login: int) -> AccountInfo:
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
