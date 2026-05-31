"""Tests for snapshot.py — round-trip, schema version guard, atomic write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.snapshot import (
    SCHEMA_VERSION,
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
    read,
    write,
)


def _account() -> AccountSnapshot:
    return AccountSnapshot(
        login=1234567,
        label="Test",
        currency="USD",
        balance=1000.0,
        equity=1000.0,
        last_success="2025-01-01T00:00:00Z",
        last_error=None,
    )


def _closed_deal(ticket: int = 1) -> ClosedDeal:
    return ClosedDeal(
        account=1234567,
        ticket=ticket,
        order=ticket * 10,
        position_id=ticket * 100,
        time=1700000000,
        time_msc=1700000000000,
        type=1,
        entry=1,
        reason=0,
        magic=0,
        volume=0.1,
        price=1.2345,
        profit=50.0,
        swap=-1.0,
        commission=-0.5,
        fee=0.0,
        symbol="EURUSD",
        comment="",
        external_id="",
    )


def _open_position(ticket: int = 1) -> OpenPosition:
    return OpenPosition(
        account=1234567,
        ticket=ticket,
        identifier=ticket * 1000,
        time=1700000000,
        time_msc=1700000000000,
        time_update=1700000500,
        time_update_msc=1700000500000,
        type=0,
        reason=0,
        magic=0,
        volume=0.2,
        price_open=1.1000,
        price_current=1.1050,
        sl=0.0,
        tp=0.0,
        profit=10.0,
        swap=0.0,
        symbol="EURUSD",
        comment="",
        external_id="",
    )


def _cash_flow(ticket: int = 1, amount: float = 1000.0) -> CashFlow:
    return CashFlow(
        account=1234567,
        ticket=ticket,
        order=0,
        position_id=0,
        time=1700000000,
        time_msc=1700000000000,
        type=2,
        entry=0,
        reason=0,
        magic=0,
        volume=0.0,
        price=0.0,
        profit=amount,
        swap=0.0,
        commission=0.0,
        fee=0.0,
        symbol="",
        comment="Deposit",
        external_id="",
    )


def _minimal_snapshot() -> Snapshot:
    return Snapshot(
        schema_version=2,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[_closed_deal()],
        open_positions=[_open_position()],
        cash_flows=[_cash_flow()],
    )


# ─── round-trip ──────────────────────────────────────────────────────────────


def test_write_read_roundtrip(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap = _minimal_snapshot()
    write(snap_path, snap)
    result = read(snap_path)
    assert result.schema_version == snap.schema_version
    assert result.generated_at == snap.generated_at
    assert len(result.accounts) == 1
    assert result.accounts[0].login == 1234567
    assert result.accounts[0].balance == 1000.0
    assert len(result.closed_deals) == 1
    assert result.closed_deals[0].ticket == 1
    assert result.closed_deals[0].profit == 50.0
    assert result.closed_deals[0].symbol == "EURUSD"
    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticket == 1
    assert result.open_positions[0].price_current == 1.1050
    assert len(result.cash_flows) == 1
    assert result.cash_flows[0].profit == 1000.0
    assert result.cash_flows[0].comment == "Deposit"


def test_empty_collections_roundtrip(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap = Snapshot(
        schema_version=2,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[],
        open_positions=[],
        cash_flows=[],
    )
    write(snap_path, snap)
    result = read(snap_path)
    assert result.closed_deals == []
    assert result.open_positions == []
    assert result.cash_flows == []


def test_write_sets_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    assert raw["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == 2


# ─── schema version guard ────────────────────────────────────────────────────


def test_read_rejects_wrong_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    raw["schema_version"] = SCHEMA_VERSION - 1
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path)


def test_read_rejects_missing_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    del raw["schema_version"]
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path)


def test_read_error_mentions_repoll(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    raw["schema_version"] = 999
    snap_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="poll"):
        read(snap_path)


def test_read_rejects_corrupt_json(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text("{not valid json")
    with pytest.raises(ValueError, match="corrupt"):
        read(snap_path)


def test_read_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="poll"):
        read(tmp_path / "nonexistent.json")


# ─── atomic write ────────────────────────────────────────────────────────────


def test_write_no_tmp_file_after_success(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    tmp = snap_path.with_suffix(".tmp")
    assert not tmp.exists()
    assert snap_path.exists()


def test_write_failure_leaves_destination_unchanged(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    original = _minimal_snapshot()
    write(snap_path, original)
    original_text = snap_path.read_text()

    modified = Snapshot(
        schema_version=2,
        generated_at="2025-06-01T00:00:00Z",
        accounts=original.accounts,
        closed_deals=original.closed_deals,
        open_positions=original.open_positions,
        cash_flows=original.cash_flows,
    )
    with (
        patch.object(Path, "replace", side_effect=OSError("simulated rename failure")),
        pytest.raises(OSError),
    ):
        write(snap_path, modified)

    assert snap_path.read_text() == original_text
