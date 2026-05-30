"""Schema file staleness check — fails if the committed file drifts from the models."""

from __future__ import annotations

import json
from pathlib import Path

from mt5_pnl_exporter.snapshot import Snapshot

_SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "snapshot.schema.json"


def test_schema_file_matches_models() -> None:
    expected = json.dumps(Snapshot.model_json_schema(), indent=2) + "\n"
    actual = _SCHEMA_PATH.read_text()
    assert actual == expected, (
        "schema/snapshot.schema.json is out of date. Run: uv run mt5-pnl-exporter schema"
    )
