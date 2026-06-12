# CLAUDE.md

MT5 P&L exporter: a `uv`-managed Python 3.12 CLI (`mt5-pnl-exporter`) that exports MT5 deal history on demand on the Windows host where MT5 runs and writes `snapshot.json`. The schema lives
in `schema/snapshot.schema.json`; consumers (CLI, UI) read the snapshot against
the schema. See [`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract.

## Commands

```bash
uv sync                                # install dev deps
uv sync --extra mt5                    # Windows host: also install MetaTrader5
uv run pytest                          # tests (coverage = 100%; schema staleness check included)
uv run mt5-pnl-exporter set-encryption-passphrase  # set passphrase used for snapshot encryption
uv run mt5-pnl-exporter export                 # run a real export (Windows + creds)
uv run mt5-pnl-exporter schema         # regenerate schema/snapshot.schema.json
uv run twine check --strict dist/*             # validate built artifacts before release
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
uv run pre-commit install              # gitleaks secret-scan hook
```

## Architecture

- `cli.py` — Typer app; commands: `export`, `set-investor-password`, `set-encryption-passphrase`, `schema`.
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only) is the sole implementation.
- `snapshot.py` — typed pydantic models for `AccountSnapshot`, `ClosedDeal`, `OpenPosition`, `CashFlow` + atomic `write` (temp file + `replace`). `write` and `read` chain `JSON → gzip → age (passphrase)` on disk; both take the passphrase as a required argument. `read()` accepts same-major snapshots up to its own minor (currently `"1.0"`); rejects others with a readable error. One record per closed deal, position, and cash flow — no pre-aggregation.
- `config.py` — pydantic models + YAML loader. Flat shape: `snapshot_path`, `terminal_path`, `accounts` at the top level. `snapshot_path` expands `~` at load time.
- `secrets.py` — keyring access and log redaction.
- `schema/snapshot.schema.json` — generated from the pydantic `Snapshot` model. `tests/test_schema_file.py` fails CI if it drifts.

## Gotchas

- **Never import `MetaTrader5` at module level.** It is deferred inside `MT5Source` (sources/mt5.py).
- **Investor passwords only**, stored in the OS keychain via `keyring` on the Windows host. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `export` only.
- **Typer pretty exceptions are disabled on purpose** (`pretty_exceptions_enable=False` in cli.py). Rich tracebacks render local variables, which after secret resolution would print the encryption passphrase and investor passwords to stderr — `redact_filter` only covers `logging` output. Don't re-enable them for prettier crashes. Expected errors (missing config, missing keyring entries) are caught in `export` and printed as curated one-liners.
- **Snapshot is mandatorily age-encrypted** with a keychain-stored passphrase (account `encryption-passphrase` on `KEYRING_SERVICE`). `snapshot.read()` and `snapshot.write()` both require the passphrase; `export` refuses to run if it's unset (`set-encryption-passphrase` first). Consumers must reverse the same `gzip → age` pipeline.
- **`export` tolerates an unreadable prior snapshot.** It reads the existing snapshot first (to carry account data forward and to decide whether to keep the previous file when all accounts fail). If that file is missing *or* can't be decoded (wrong passphrase after a `set-encryption-passphrase` change, corrupt, or unsupported schema), `export` logs a warning and regenerates rather than crashing — the prior read is only an optimisation. It catches both `FileNotFoundError` and `ValueError` at the call site; `snapshot.read()` itself stays strict.
- **A dedicated MT5 terminal is required**: `mt5.login()` switches the terminal's active account, so pointing it at an EA terminal logs the EA out.
- **MT5 history sync is async.** `_get_history_raw()` waits for `history_deals_total(from, to)` to stabilise before calling `history_deals_get()`.
- **Deal classification**: `MT5Source.fetch_closed_deals` keeps only `DEAL_ENTRY_OUT`/`INOUT`/`OUT_BY` records with non-balance-family types (all three carry realised P&L; `INOUT` is a reversal, `OUT_BY` a close-by). `fetch_cash_flows` keeps only balance-family types (`BALANCE`, `CREDIT`, `CHARGE`, `CORRECTION`, `BONUS`, `COMMISSION`). `_get_history_raw` memoises `history_deals_get` per `(login, date_from, date_to)` so the two fetchers share one round-trip to MT5.
- **Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`. `tests/test_schema_file.py` catches missed regenerations.
- **`SCHEMA_VERSION` is `"1.0"`** (major.minor string). `read()` accepts the same major up to its own minor; bump the minor for additive fields, the major for breaking changes.
- **`export` is one-shot and manual.** It fetches once and exits — there is no polling loop or daemon. v1 is run-on-demand by design; no scheduler recipe ships (a low-frequency schedule would only serve stale equity and open positions by viewing time). If scheduling is ever added, a Windows Task Scheduler task must run as the same user that holds the keychain entries, in "run only when logged on" mode, or `keyring` cannot read the credential vault.
- **Dependencies are Renovate-managed; don't hand-bump them.** GitHub Actions in `.github/workflows/` are pinned to commit SHAs (with a trailing version comment) and Python deps in `pyproject.toml`/`uv.lock` are tracked by `renovate.json`. Renovate opens the update PRs (digest/minor/patch auto-merge on green CI; majors and `MetaTrader5` open a PR). Do not replace a pinned SHA with a tag or manually bump a version — it fights the bot. Releases publish to PyPI via Trusted Publishing in `.github/workflows/release.yml` (published GitHub Release → PyPI; `workflow_dispatch` → TestPyPI); see CONTRIBUTING.md's "Releasing" section.

## Conventions

- NZ English in comments and docs (realise, behaviour, colour). No hyperbole.
- Python 3.12+; `from __future__ import annotations` in every module.
- Tests target `snapshot.py` (round-trip) and `sources/mt5.py` (call-shape + field-copy fidelity via a fake MetaTrader5 module). End-to-end CLI tests inject an in-test fake `DataSource` in place of `MT5Source`.
- After changing commands, architecture, or a gotcha above, update this file and README.md in the same change.
