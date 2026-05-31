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
