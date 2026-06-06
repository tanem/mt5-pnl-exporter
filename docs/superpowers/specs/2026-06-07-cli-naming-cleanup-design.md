# CLI naming cleanup + manual-export framing

Date: 2026-06-07
Status: Approved (design)

## Background

The original `mt5-pnl` repo documented a Windows Task Scheduler recipe for
running the CLI on an interval. While considering whether to port that recipe
to this repo, two things became clear:

1. The code never actually polled. The `poll` command runs a single
   fetch-and-write and exits (`cli.py`) — there is no loop, daemon, or
   interval. "Polling" only ever lived in the command name and the external
   scheduler idea.
2. For the intended usage — looking at the snapshot occasionally and
   on-demand — a once-daily scheduled run produces stale `balance`/`equity`
   and `open_positions` by viewing time. Running the command by hand right
   before you look gives fresher data than any low-frequency schedule.

So for v1 the tool is a **manual, on-demand exporter**. This makes the `poll`
name misleading and is a good moment to align the whole CLI surface with what
the tool actually does. Nothing has been released and there are no external
consumers, so breaking changes are free.

## Goals

- Rename CLI commands so each name matches its one-shot, manual behaviour.
- Remove remaining internal naming inconsistencies surfaced during the audit.
- Document the tool as a manual on-demand exporter; do **not** add a Windows
  Task Scheduler recipe for v1.

## Non-goals

- No scheduling/daemon feature, and no scheduling documentation.
- No change to the MT5-mirrored deal/position field names (verbatim fidelity
  to MT5's `TradeDeal`/`TradePosition` is a deliberate contract).
- No change to the distribution/package/entry-point name `mt5-pnl-exporter`,
  the keyring service name, or the `snapshot.json.gz.age` file convention.

## Changes

### A. CLI commands

| Before | After | Reason |
|---|---|---|
| `poll` | `export` | One-shot fetch-and-write from a tool literally called an *exporter*. Verb stays distinct from the "snapshot" noun. |
| `set-password` | `set-investor-password` | Parallels `set-encryption-passphrase`, removes "which password?" ambiguity, matches the `set_investor_password()` function. |
| `set-encryption-passphrase` | (unchanged) | Already unambiguous and self-documenting. |
| `schema` | (unchanged) | Maintainer-only regen command; keeps the noun the rest of the codebase uses. |

Final command surface: `export` · `set-investor-password` ·
`set-encryption-passphrase` · `schema`.

### B. Internal consistency

- `DataSource.account_info()` → `fetch_account_info()` so all four protocol
  methods share the `fetch_*` prefix (`base.py`, `MT5Source` in
  `sources/mt5.py`, and the in-test fake `DataSource`).

### C. Schema field

- `AccountSnapshot.last_success` → `last_success_at`. It holds an ISO
  timestamp, but the bare name reads like a boolean; `last_success_at` pairs
  with `generated_at`. Its sibling `last_error` stays (it is a message, not a
  time).
- This is a model change: regenerate `schema/snapshot.schema.json`. As nothing
  consumes the field yet, treat it as part of this pre-release reshape and keep
  `SCHEMA_VERSION` at `"1.0"`.

### D. Deliberately unchanged (considered, not changing)

- Distribution/package/entry-point `mt5-pnl-exporter` — "exporter" now matches
  `export`.
- MT5-mirrored deal/position fields (`ticket`, `time_msc`, `type`, `entry`,
  `magic`, `external_id`, …).
- Model names `Snapshot` / `AccountSnapshot` / `ClosedDeal` / `OpenPosition` /
  `CashFlow`.
- `KEYRING_SERVICE`, the `encryption-passphrase` keyring account label, and the
  `snapshot.json.gz.age` convention.

## Affected files / ripple

- `src/mt5_pnl_exporter/cli.py` — command names and `@app.command` decorators;
  the module header docstring (`poll | set-password | schema`); the Typer app
  `help` description; the `poll`/`set-password` command docstrings.
- User-facing hint/error strings that name old commands:
  `snapshot.py` (the `read()` FileNotFoundError and unsupported-version
  messages reference `'poll'`), `config.py` (`resolve_passwords` references
  `set-password`).
- `src/mt5_pnl_exporter/snapshot.py` — rename `last_success` field; regen schema.
- `src/mt5_pnl_exporter/sources/base.py` and `sources/mt5.py` —
  `account_info` → `fetch_account_info`.
- `schema/snapshot.schema.json` — regenerate via `mt5-pnl-exporter schema`.
- Tests — update command invocations (`poll` → `export`, `set-password` →
  `set-investor-password`), the in-test fake `DataSource` method name, and any
  assertions on the `last_success` field or hint strings.
- `README.md` — quick-start, Commands list, and any prose referencing `poll`;
  no scheduling section added; frame `export` as a manual on-demand command.
- `CLAUDE.md` — Commands block, the gotchas that name `poll`/`set-password`,
  and a note that scheduling is intentionally out of scope for v1 (manual run).

## Verification

- `uv run pytest` green at 100% coverage (includes the schema-staleness check,
  which guards the regen).
- `uv run ruff check src/ tests/` and `uv run mypy src/mt5_pnl_exporter` clean.
- `grep` confirms no lingering references to `poll`, `set-password`, or
  `last_success` in `src/`, `tests/`, `README.md`, `CLAUDE.md`, or the schema.
