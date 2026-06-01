# mt5-pnl-exporter

Polls MT5 deal history on a Windows VPS and writes `snapshot.json` — the
published contract that downstream tools (CLI, UI) consume.

Part of the mt5-pnl tool family. See
[`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract and the wider design.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # VPS, includes MetaTrader5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Quick start (VPS)

```bash
mt5-pnl-exporter set-password 1234567        # store investor pw in keychain
mt5-pnl-exporter set-encryption-passphrase   # store snapshot encryption passphrase in keychain
cp config.example.yaml config.yaml           # then chmod 600 config.yaml
mt5-pnl-exporter poll                        # writes snapshot.json.gz.age
```

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json` atomically.
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain (`keyring`).
- `mt5-pnl-exporter set-encryption-passphrase` — store the snapshot encryption passphrase in the OS keychain (entered twice).
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic `Snapshot` model.

## Schema

`schema/snapshot.schema.json` is generated from the pydantic models and
committed. CI (`tests/test_schema_file.py`) fails if it drifts. Consumers
vendor the file from a specific release. The on-disk file is the schema's
JSON gzipped then encrypted with [age](https://age-encryption.org/)
under a passphrase from the OS keychain — consumers must reverse the
same pipeline to read it.

The snapshot carries one record per closed deal (`ClosedDeal`), open
position (`OpenPosition`), and balance-family deal — deposit, withdrawal,
credit, charge, correction, bonus, commission (`CashFlow`). Plus one
`AccountSnapshot` per account with balance, equity, currency, and the
last-success/last-error stamps. No pre-aggregation — consumers slice the
raw records however they want.

Schema version stamping is a plain integer (`SCHEMA_VERSION = 2`) in 0.x.
`major.minor` versioning ships in the 1.0 release (Phase 1b cycle 4).

## Snapshot size

The snapshot stores one record per closed deal, so it grows with trading
volume. Rough sizing: ~350 bytes per closed-deal record. Ten accounts
with two years of 50-deals-per-day-per-account history (~250 trading
days/year) is around 90 MB; busier setups (200 deals/day) reach ~350 MB.
Each `poll` gzips the JSON before encrypting, so the on-disk file is
roughly an order of magnitude smaller — the 350 MB worst case lands at
~35 MB on disk, which is what sync services (Dropbox, Syncthing) see.

## Status

0.x — pre-release. Schema may still change. Tag `1.0` ships in Phase 1b once
the planned simplifications have landed.
