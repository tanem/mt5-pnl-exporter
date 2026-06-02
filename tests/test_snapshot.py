"""Tests for snapshot.py — encrypted round-trip, schema guard, atomic write."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from unittest.mock import patch

import pyrage
import pytest

from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
    _parse_version,
    read,
    write,
)

PASSPHRASE = "correct horse battery staple"


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
        schema_version="1.0",
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[_closed_deal()],
        open_positions=[_open_position()],
        cash_flows=[_cash_flow()],
    )


# ─── round-trip ──────────────────────────────────────────────────────────────


def test_write_read_roundtrip_all_record_types(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    snap = _minimal_snapshot()
    write(snap_path, snap, PASSPHRASE)
    result = read(snap_path, PASSPHRASE)
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
    snap_path = tmp_path / "snapshot.json.gz.age"
    snap = Snapshot(
        schema_version="1.0",
        generated_at="2025-01-01T00:00:00Z",
        accounts=[_account()],
        closed_deals=[],
        open_positions=[],
        cash_flows=[],
    )
    write(snap_path, snap, PASSPHRASE)
    result = read(snap_path, PASSPHRASE)
    assert result.closed_deals == []
    assert result.open_positions == []
    assert result.cash_flows == []


def test_written_file_is_not_plaintext_json(tmp_path):
    """Smoke test that the on-disk bytes are encrypted, not plaintext JSON."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    raw = snap_path.read_bytes()
    assert b"schema_version" not in raw
    assert b"EURUSD" not in raw


# ─── decryption errors ───────────────────────────────────────────────────────


def test_read_wrong_passphrase_raises_value_error(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    with pytest.raises(ValueError, match="wrong passphrase or corrupt file"):
        read(snap_path, "not-the-passphrase")


def test_read_truncated_file_raises_value_error(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    raw = snap_path.read_bytes()
    snap_path.write_bytes(raw[: len(raw) // 2])
    with pytest.raises(ValueError, match="wrong passphrase or corrupt file"):
        read(snap_path, PASSPHRASE)


def test_read_corrupt_gzip_after_decrypt_raises_value_error(tmp_path):
    """Decryption succeeds but the inner gzip is garbage — same ValueError."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    bogus_inner = b"this is not a gzip stream"
    encrypted = pyrage.passphrase.encrypt(bogus_inner, PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="wrong passphrase or corrupt file"):
        read(snap_path, PASSPHRASE)


# ─── missing passphrase ──────────────────────────────────────────────────────


def test_read_none_passphrase_raises_runtime_error(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    with pytest.raises(RuntimeError, match="no encryption passphrase set in keychain"):
        read(snap_path, None)  # type: ignore[arg-type]


def test_write_empty_passphrase_raises_runtime_error(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    with pytest.raises(RuntimeError, match="no encryption passphrase set in keychain"):
        write(snap_path, _minimal_snapshot(), "")


# ─── schema-version guard (still runs on the decrypted JSON) ─────────────────


def test_read_rejects_wrong_schema_version_after_decrypt(tmp_path):
    """Encrypt a v2.0-tagged blob, read it, expect the unsupported-version rejection."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "2.0",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)


def test_read_rejects_missing_schema_version_after_decrypt(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="must be a string"):
        read(snap_path, PASSPHRASE)


def test_read_corrupt_json_after_decrypt_raises_value_error(tmp_path):
    """gzip decompresses successfully but the inner bytes are not valid JSON."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    valid_gzip_bad_json = gzip.compress(b"{this is not json")
    encrypted = pyrage.passphrase.encrypt(valid_gzip_bad_json, PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="corrupt"):
        read(snap_path, PASSPHRASE)


def test_read_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="poll"):
        read(tmp_path / "nonexistent.json.gz.age", PASSPHRASE)


# ─── atomic write ────────────────────────────────────────────────────────────


def test_write_no_tmp_file_after_success(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    tmp = snap_path.with_suffix(".tmp")
    assert not tmp.exists()
    assert snap_path.exists()


def test_write_failure_leaves_destination_unchanged(tmp_path):
    snap_path = tmp_path / "snapshot.json.gz.age"
    original = _minimal_snapshot()
    write(snap_path, original, PASSPHRASE)
    original_bytes = snap_path.read_bytes()

    modified = Snapshot(
        schema_version="1.0",
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
        write(snap_path, modified, PASSPHRASE)

    assert snap_path.read_bytes() == original_bytes


def test_parse_version_accepts_major_minor():
    assert _parse_version("1.0") == (1, 0)
    assert _parse_version("2.7") == (2, 7)


def test_parse_version_rejects_non_string():
    with pytest.raises(ValueError, match="must be a string"):
        _parse_version(2)


def test_parse_version_rejects_wrong_shape():
    for bad in ("1", "1.0.0", "1.a", ""):
        with pytest.raises(ValueError, match=r"major\.minor"):
            _parse_version(bad)


def test_read_rejects_future_minor(tmp_path):
    """Stamp from a newer minor (1.1) is rejected by a 1.0 reader."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "1.1",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)


def test_read_rejects_future_major(tmp_path):
    """Stamp from a newer major (2.0) is rejected by a 1.0 reader."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "2.0",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)


def test_read_accepts_exact_current_version(tmp_path):
    """Sanity: a 1.0 stamp round-trips without rejection."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    result = read(snap_path, PASSPHRASE)
    assert result.schema_version == "1.0"
