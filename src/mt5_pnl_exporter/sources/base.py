"""DataSource protocol — swappable backend (MT5, fixture, future MetaApi)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

# MT5 deal type/entry constants shared across aggregate.py and sources/mt5.py
# (see sources/mt5.py and aggregate.py — import from here, not redefined there)
DEAL_TYPE_BALANCE = 2
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 3


class Deal(BaseModel):
    ticket: int
    account: int
    time: int  # Unix timestamp (deal close time)
    type: int  # mt5 DEAL_TYPE_*
    entry: int  # mt5 DEAL_ENTRY_*
    profit: float
    swap: float
    commission: float
    fee: float


class AccountInfo(BaseModel):
    login: int
    label: str
    currency: str
    balance: float
    equity: float


@runtime_checkable
class DataSource(Protocol):
    def fetch_deals(self, login: int, date_from: int, date_to: int) -> list[Deal]: ...
    def account_info(self, login: int) -> AccountInfo: ...
