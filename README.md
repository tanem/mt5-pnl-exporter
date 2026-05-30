# mt5-pnl-exporter

Polls MT5 deal history on a Windows VPS and writes `snapshot.json` — the
published contract that downstream tools (CLI, UI) consume.

Part of the mt5-pnl tool family. See
[`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract and the wider design.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # VPS, includes MetaTrader5
uv tool install mt5-pnl-exporter          # any OS, schema/smoke-test work
```

## Quick start (VPS)

```bash
mt5-pnl-exporter set-password 1234567        # store investor pw in keychain
cp config.example.yaml config.yaml           # then chmod 600 config.yaml
mt5-pnl-exporter poll                        # writes snapshot.json
```

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json` atomically.
- `mt5-pnl-exporter poll --source fixture` — write a snapshot from `tests/fixtures/sample_deals.json` (smoke test, no creds).
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain (`keyring`).
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic `Snapshot` model.

## Schema

`schema/snapshot.schema.json` is generated from the pydantic models and
committed. CI (`tests/test_schema_file.py`) fails if it drifts. Consumers
vendor the file from a specific release.

Schema version stamping is a plain integer (`SCHEMA_VERSION = 1`) in 0.x.
`major.minor` versioning ships in the 1.0 release (Phase 1b of the repo split).

## Status

0.x — pre-release. Schema may still change. Tag `1.0` ships in Phase 1b once
the planned simplifications have landed.
