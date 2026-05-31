# CLAUDE.md

MT5 P&L exporter: a `uv`-managed Python 3.12 CLI (`mt5-pnl-exporter`) that polls
MT5 deal history on a Windows VPS and writes `snapshot.json`. The schema lives
in `schema/snapshot.schema.json`; consumers (CLI, UI) read the snapshot against
the schema. See [`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract.

## Commands

```bash
uv sync                                # install dev deps
uv sync --extra mt5                    # VPS: also install MetaTrader5
uv run pytest                          # tests (coverage ≥95%; schema staleness check included)
uv run mt5-pnl-exporter poll                   # run a real poll (Windows + creds)
uv run mt5-pnl-exporter schema         # regenerate schema/snapshot.schema.json
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
uv run pre-commit install              # gitleaks secret-scan hook
```

## Architecture

- `cli.py` — Typer app; commands: `poll`, `set-password`, `schema`.
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only) is the sole implementation.
- `snapshot.py` — typed pydantic models for `AccountSnapshot`, `ClosedDeal`, `OpenPosition`, `CashFlow` + atomic `write` (temp file + `replace`). `read()` rejects mismatched `SCHEMA_VERSION` (currently `2`). One record per closed deal, position, and cash flow — no pre-aggregation.
- `config.py` — pydantic models + YAML loader. Flat shape: `snapshot_path`, `terminal_path`, `accounts` at the top level.
- `secrets.py` — keyring access and log redaction.
- `schema/snapshot.schema.json` — generated from the pydantic `Snapshot` model. `tests/test_schema_file.py` fails CI if it drifts.

## Gotchas

- **Never import `MetaTrader5` at module level.** It is deferred inside `MT5Source` (sources/mt5.py).
- **Investor passwords only**, stored in the VPS keychain via `keyring`. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `poll` only.
- **A dedicated MT5 terminal is required**: `mt5.login()` switches the terminal's active account, so pointing it at an EA terminal logs the EA out.
- **MT5 history sync is async.** `_get_history_raw()` waits for `history_deals_total(from, to)` to stabilise before calling `history_deals_get()`.
- **Deal classification**: `MT5Source.fetch_closed_deals` keeps only `DEAL_ENTRY_OUT`/`INOUT` records with non-balance-family types. `fetch_cash_flows` keeps only balance-family types (`BALANCE`, `CREDIT`, `CHARGE`, `CORRECTION`, `BONUS`, `COMMISSION`). `_get_history_raw` memoises `history_deals_get` per `(login, date_from, date_to)` so the two fetchers share one round-trip to MT5.
- **Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`. `tests/test_schema_file.py` catches missed regenerations.
- **`SCHEMA_VERSION` is `2`** (plain integer). Major.minor versioning lands in Phase 1b cycle 4.

## Conventions

- NZ English in comments and docs (realise, behaviour, colour). No hyperbole.
- Python 3.12+; `from __future__ import annotations` in every module.
- Tests target `snapshot.py` (round-trip) and `sources/mt5.py` (call-shape + field-copy fidelity via a fake MetaTrader5 module). End-to-end CLI tests inject an in-test fake `DataSource` in place of `MT5Source`.
- After changing commands, architecture, or a gotcha above, update this file and README.md in the same change.
