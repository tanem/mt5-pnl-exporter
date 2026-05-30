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
uv run mt5-pnl-exporter poll --source fixture   # smoke-test without creds
uv run mt5-pnl-exporter schema         # regenerate schema/snapshot.schema.json
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
uv run pre-commit install              # gitleaks secret-scan hook
```

## Architecture

- `cli.py` — Typer app; commands: `poll`, `set-password`, `schema`.
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only); `FixtureSource` (local JSON for dev / tests).
- `aggregate.py` — `deals_to_daily()` runs inside `poll`.
- `snapshot.py` — typed pydantic models + atomic `write` (temp file + `replace`). `read()` rejects mismatched `SCHEMA_VERSION`.
- `config.py` — pydantic models + YAML loader. Poll-side only — no query-side config (`account_groups`, `staleness_warn_hours`) here.
- `secrets.py` — keyring access and log redaction.
- `schema/snapshot.schema.json` — generated from the pydantic `Snapshot` model. `tests/test_schema_file.py` fails CI if it drifts.

## Gotchas

- **Never import `MetaTrader5` at module level.** It is deferred inside `MT5Source` (sources/mt5.py).
- **Investor passwords only**, stored in the VPS keychain via `keyring`. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `poll` only.
- **A dedicated MT5 terminal is required**: `mt5.login()` switches the terminal's active account, so pointing it at an EA terminal logs the EA out.
- **MT5 history sync is async.** `fetch_deals()` waits for `history_deals_total(from, to)` to stabilise before calling `history_deals_get()`.
- **Deal filtering**: only `DEAL_ENTRY_OUT`/`INOUT` closing deals count; `DEAL_TYPE_BALANCE` is excluded. Net P&L = profit+swap+commission+fee; net of exactly 0 counts as a win.
- **Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`. `tests/test_schema_file.py` catches missed regenerations.
- **`SCHEMA_VERSION` is still a plain integer** in 0.x. Major.minor versioning ships in Phase 1b.

## Conventions

- NZ English in comments and docs (realise, behaviour, colour). No hyperbole.
- Python 3.12+; `from __future__ import annotations` in every module.
- Tests target `aggregate.py` and `snapshot.py`. Use `FixtureSource` instead of mocking MT5.
- After changing commands, architecture, or a gotcha above, update this file and README.md in the same change.
