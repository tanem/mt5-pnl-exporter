"""Tests for aggregate.py — the correctness core."""

from __future__ import annotations

import datetime

import pytest

from mt5_pnl_exporter.aggregate import deals_to_daily
from mt5_pnl_exporter.sources.base import Deal

# DEAL_TYPE_* constants
TYPE_BUY = 0
TYPE_SELL = 1
TYPE_BALANCE = 2
# DEAL_ENTRY_*
ENTRY_IN = 0
ENTRY_OUT = 1
ENTRY_INOUT = 3

_JAN_1 = int(datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.UTC).timestamp())
_JAN_2 = int(datetime.datetime(2025, 1, 2, 12, 0, tzinfo=datetime.UTC).timestamp())


def _deal(
    account=1,
    time=_JAN_1,
    type_=TYPE_BUY,
    entry=ENTRY_OUT,
    profit=10.0,
    swap=-0.5,
    commission=-0.2,
    fee=0.0,
    ticket=1,
) -> Deal:
    return Deal(
        ticket=ticket,
        account=account,
        time=time,
        type=type_,
        entry=entry,
        profit=profit,
        swap=swap,
        commission=commission,
        fee=fee,
    )


# ─── deals_to_daily ──────────────────────────────────────────────────────────


def test_deals_to_daily_basic():
    deals = [_deal(profit=10.0, swap=-1.0, commission=-0.5)]
    rows = deals_to_daily(deals)
    assert len(rows) == 1
    assert rows[0].pnl == pytest.approx(8.5)
    assert rows[0].trades == 1
    assert rows[0].wins == 1
    assert rows[0].losses == 0


def test_deals_to_daily_excludes_balance_deals():
    deals = [
        _deal(profit=10.0, swap=0, commission=0),
        _deal(type_=TYPE_BALANCE, entry=ENTRY_IN, profit=5000.0, swap=0, commission=0, ticket=99),
    ]
    rows = deals_to_daily(deals)
    assert len(rows) == 1
    assert rows[0].pnl == pytest.approx(10.0)


def test_deals_to_daily_excludes_entry_in():
    deals = [
        _deal(profit=10.0, swap=0, commission=0, entry=ENTRY_OUT),
        _deal(profit=50.0, swap=0, commission=0, entry=ENTRY_IN, ticket=2),  # open side — excluded
    ]
    rows = deals_to_daily(deals)
    assert len(rows) == 1
    assert rows[0].pnl == pytest.approx(10.0)


def test_deals_to_daily_includes_inout():
    deals = [_deal(profit=20.0, entry=ENTRY_INOUT, swap=-1.0, commission=-0.5)]
    rows = deals_to_daily(deals)
    assert rows[0].pnl == pytest.approx(18.5)


def test_deals_to_daily_multi_day_multi_account():
    deals = [
        _deal(account=1, time=_JAN_1, profit=10.0, swap=0, commission=0, ticket=1),
        _deal(account=1, time=_JAN_2, profit=-5.0, swap=0, commission=0, ticket=2),
        _deal(account=2, time=_JAN_1, profit=20.0, swap=0, commission=0, ticket=3),
    ]
    rows = deals_to_daily(deals)
    by_key = {(r.account, r.date): r for r in rows}
    assert by_key[(1, "2025-01-01")].pnl == pytest.approx(10.0)
    assert by_key[(1, "2025-01-02")].pnl == pytest.approx(-5.0)
    assert by_key[(2, "2025-01-01")].pnl == pytest.approx(20.0)


def test_deals_to_daily_win_loss_counts():
    deals = [
        _deal(profit=10.0, swap=0, commission=0, ticket=1),
        _deal(profit=-5.0, swap=0, commission=0, ticket=2),
        _deal(profit=0.0, swap=0, commission=0, ticket=3),  # zero = win
    ]
    rows = deals_to_daily(deals)
    assert rows[0].wins == 2
    assert rows[0].losses == 1
