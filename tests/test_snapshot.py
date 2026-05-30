"""Tests for snapshot.py — round-trip, schema version guard, atomic write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.snapshot import (
    SCHEMA_VERSION,
    AccountSnapshot,
    DailyRow,
    Snapshot,
    read,
    write,
)


def _minimal_snapshot() -> Snapshot:
    return Snapshot(
        schema_version=1,
        generated_at="2025-01-01T00:00:00Z",
        accounts=[
            AccountSnapshot(
                login=1234567,
                label="Test",
                currency="USD",
                balance=1000.0,
                equity=1000.0,
                last_success="2025-01-01T00:00:00Z",
                last_error=None,
            )
        ],
        daily=[
            DailyRow(
                account=1234567,
                date="2025-01-01",
                pnl=10.0,
                trades=1,
                wins=1,
                losses=0,
                gross_profit=10.0,
                gross_loss=0.0,
            )
        ],
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
    assert len(result.daily) == 1
    assert result.daily[0].pnl == 10.0


def test_write_sets_schema_version(tmp_path):
    snap_path = tmp_path / "snapshot.json"
    write(snap_path, _minimal_snapshot())
    raw = json.loads(snap_path.read_text())
    assert raw["schema_version"] == SCHEMA_VERSION


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
        schema_version=1,
        generated_at="2025-06-01T00:00:00Z",
        accounts=original.accounts,
        daily=original.daily,
    )
    with (
        patch.object(Path, "replace", side_effect=OSError("simulated rename failure")),
        pytest.raises(OSError),
    ):
        write(snap_path, modified)

    assert snap_path.read_text() == original_text
