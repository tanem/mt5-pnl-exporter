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
    def fetch_closed_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]: ...
    def fetch_open_positions(self, login: int) -> list[OpenPosition]: ...
    def fetch_cash_flows(self, login: int, date_from: int, date_to: int) -> list[CashFlow]: ...
    def shutdown(self) -> None: ...
