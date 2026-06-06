"""Snapshot read/write — gzip + age pipeline, atomic temp+rename on write.

Pipeline (left-to-right on write, right-to-left on read):

    Snapshot model → JSON bytes → gzip → age (passphrase) → file

The file convention is `snapshot.json.gz.age`. Consumers must implement
the same pipeline in reverse to read it.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Literal

import pyrage
from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"
_MAJOR = 1
_MINOR = 0


def _parse_version(stamp: object) -> tuple[int, int]:
    if not isinstance(stamp, str):
        raise ValueError(f"schema_version must be a string like '1.0', got {stamp!r}")
    parts = stamp.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"schema_version {stamp!r} is not in major.minor form")
    return int(parts[0]), int(parts[1])


_MISSING_PASSPHRASE_MSG = (
    "no encryption passphrase set in keychain.\n"
    "Run 'mt5-pnl-exporter set-encryption-passphrase' first."
)


class AccountSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    login: int
    label: str
    currency: str
    balance: float
    equity: float
    last_success_at: str | None
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
    schema_version: Literal["1.0"]
    generated_at: str
    accounts: list[AccountSnapshot]
    closed_deals: list[ClosedDeal]
    open_positions: list[OpenPosition]
    cash_flows: list[CashFlow]


def write(path: Path, snap: Snapshot, passphrase: str) -> None:
    if not passphrase:
        raise RuntimeError(_MISSING_PASSPHRASE_MSG)
    data = snap.model_dump_json(indent=2).encode()
    compressed = gzip.compress(data, compresslevel=9)
    encrypted = pyrage.passphrase.encrypt(compressed, passphrase)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(encrypted)
    tmp.replace(path)


def read(path: Path, passphrase: str | None) -> Snapshot:
    if not passphrase:
        raise RuntimeError(_MISSING_PASSPHRASE_MSG)
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {path}\n"
            "Run 'mt5-pnl-exporter poll' on the Windows host first to generate it."
        )
    encrypted = path.read_bytes()
    try:
        compressed = pyrage.passphrase.decrypt(encrypted, passphrase)
        data = gzip.decompress(compressed)
    except (pyrage.DecryptError, OSError, EOFError, gzip.BadGzipFile) as exc:
        raise ValueError(
            f"Snapshot at {path} could not be decrypted — wrong passphrase or corrupt file."
        ) from exc
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Snapshot file is corrupt at {path}; re-run 'mt5-pnl-exporter poll' to regenerate."
        ) from exc
    file_major, file_minor = _parse_version(raw.get("schema_version"))
    if file_major != _MAJOR or file_minor > _MINOR:
        raise ValueError(
            f"Snapshot schema_version {raw.get('schema_version')!r} is not "
            f"supported by this reader (accepts {_MAJOR}.0–{_MAJOR}.{_MINOR}). "  # noqa: RUF001
            "Upgrade mt5-pnl-exporter, or re-run 'poll' on a compatible host."
        )
    return Snapshot.model_validate(raw)
