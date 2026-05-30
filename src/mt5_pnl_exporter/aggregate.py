"""Aggregation: closing deals → per-account-per-day buckets."""

from __future__ import annotations

import datetime
from typing import Any

from mt5_pnl_exporter.snapshot import DailyRow
from mt5_pnl_exporter.sources.base import (
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BALANCE,
    Deal,
)


def deals_to_daily(deals: list[Deal]) -> list[DailyRow]:
    """Aggregate closing deals into per-account per-day buckets."""
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for d in deals:
        # MT5Source pre-filters; FixtureSource does not — this filter handles both
        if d.type == DEAL_TYPE_BALANCE:
            continue
        if d.entry not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT):
            continue
        date = datetime.datetime.fromtimestamp(d.time, tz=datetime.UTC).strftime("%Y-%m-%d")
        key = (d.account, date)
        if key not in buckets:
            buckets[key] = {
                "account": d.account,
                "date": date,
                "pnl": 0.0,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            }
        net = d.profit + d.swap + d.commission + d.fee
        b = buckets[key]
        b["pnl"] = round(b["pnl"] + net, 2)
        b["trades"] += 1
        if net >= 0:
            b["wins"] += 1
            b["gross_profit"] = round(b["gross_profit"] + net, 2)
        else:
            b["losses"] += 1
            b["gross_loss"] = round(b["gross_loss"] + net, 2)
    return [
        DailyRow(**v) for v in sorted(buckets.values(), key=lambda r: (r["account"], r["date"]))
    ]
