"""Snapshot read/write — atomic temp+rename so a reader never sees a partial file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class AccountSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    login: int
    label: str
    currency: str
    balance: float
    equity: float
    last_success: str | None
    last_error: str | None


class DailyRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account: int
    date: str  # YYYY-MM-DD
    pnl: float
    trades: int
    wins: int
    losses: int
    gross_profit: float
    gross_loss: float


class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[1]
    generated_at: str
    accounts: list[AccountSnapshot]
    daily: list[DailyRow]
    cash_flows: list[Any] = Field(default_factory=list)


def write(path: Path, snap: Snapshot) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(snap.model_dump_json(indent=2))
    tmp.replace(path)


def read(path: Path) -> Snapshot:
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {path}\n"
            "Run 'mt5-pnl-exporter poll' on the VPS first to generate it."
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
