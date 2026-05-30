"""MT5Source — live data via the MetaTrader5 Python package (VPS/Windows only)."""

from __future__ import annotations

import datetime
import logging
import time

from mt5_pnl_exporter.sources.base import (
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BALANCE,
    AccountInfo,
    Deal,
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
                "Install with: uv sync --extra mt5  (Windows/VPS only)"
            ) from exc
        self._mt5 = mt5
        self._terminal_path = terminal_path
        self._passwords = passwords
        self._servers = servers
        self._initialized = False

    def _connect(self, login: int) -> None:
        pw = self._passwords.get(login)
        if not pw:
            raise RuntimeError(f"No investor password for login {login}")
        server = self._servers.get(login)
        if not server:
            raise RuntimeError(f"No server configured for login {login}")
        if not self._initialized:
            # Pass credentials to initialize() so it can authenticate on the
            # first call — calling initialize(path) without creds returns
            # (-6, 'Terminal: Authorization failed') on a fresh terminal.
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
        # Terminal already initialised — switch to this account.
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

    def fetch_deals(self, login: int, date_from: int, date_to: int) -> list[Deal]:
        self._connect(login)

        dt_from = datetime.datetime.fromtimestamp(date_from, tz=datetime.UTC)
        dt_to = datetime.datetime.fromtimestamp(date_to, tz=datetime.UTC)
        self._wait_history_synced(login, dt_from, dt_to)
        raw = self._mt5.history_deals_get(dt_from, dt_to)
        if raw is None:
            code, msg = self._mt5.last_error()
            if code != 1:  # 1 = ERR_SUCCESS / no deals in range
                raise RuntimeError(f"history_deals_get failed for {login}: ({code}, {msg!r})")
            return []

        deals: list[Deal] = []
        for d in raw:
            # Skip balance/deposit/withdrawal deals — not P&L
            if d.type == DEAL_TYPE_BALANCE:
                continue
            # Only closing deals contribute to realised P&L
            if d.entry not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT):
                continue
            deals.append(
                Deal(
                    ticket=d.ticket,
                    account=login,
                    time=int(d.time),
                    type=d.type,
                    entry=d.entry,
                    profit=float(d.profit),
                    swap=float(d.swap),
                    commission=float(d.commission),
                    fee=float(getattr(d, "fee", 0.0)),
                )
            )
        return deals

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
