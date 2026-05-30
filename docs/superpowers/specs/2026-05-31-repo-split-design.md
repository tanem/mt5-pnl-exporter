# Repo split plan: exporter, CLI, UI

Status: design. Approved 2026-05-31, ready to plan implementation.

## Why

`snapshot.json` is already the contract between the polling side and everything that reads it. The split exists logically today (the `mt5` extra, role-scoped `poll:` / `query:` config). The triggers to make it physical are all in play:

- A web UI is on the horizon, and a clean `snapshot.json` contract makes that cleaner than reaching into the current package.
- The "clone the repo" install is friction for VPS users — `uv tool install` from PyPI is the immediate win.
- The query CLI is being rewritten in Go for a single static binary on the query machine, with no Python runtime dependency.

Goal: composability. Multiple presentations (CLI, web UI, future consumers) on top of one well-defined producer, each evolving independently.

## Topology

Three repos, created in order, each independently versioned and released:

- **`mt5-pnl-exporter`** (Python, new repo) — owns the polling code (`poll`, `set-password`, `sources/`, `secrets.py`, `snapshot.py`), the schema, and the schema version. Publishes to PyPI as `mt5-pnl-exporter`. Installed via `uv tool install "mt5-pnl-exporter[mt5]"`.
- **`mt5-pnl-cli`** (Go, new repo) — query/reporting CLI. Reads `snapshot.json`, does its own grouping and presentation. Distributed as a single static binary, cross-compiled for Windows/macOS/Linux.
- **`mt5-pnl-ui`** (web, new repo, later) — reads `snapshot.json` directly. Tech stack decided at Phase 4.

The current `mt5-pnl` repo is deleted once `mt5-pnl-exporter` has shipped its first PyPI release and the Go CLI has reached feature parity.

### Naming — Prometheus comparison

"Exporter" is the Prometheus convention for a standalone producer (`node_exporter`, `mysqld_exporter`, `blackbox_exporter` — each its own repo under `prometheus/`). The pattern fits exactly: one producer per data source, separate repos per consumer.

There is no Prometheus-server analogue here, because `snapshot.json` *is* the store. The pattern is closer to `compile_commands.json` or SARIF than to Prometheus's TSDB.

## Schema and versioning

`schema/snapshot.schema.json` lives in `mt5-pnl-exporter`, **generated from the pydantic models** via `Snapshot.model_json_schema()`. A dedicated subcommand (or script) writes it; CI fails if the committed file is stale. Single source of truth — code — with the schema file derived.

The version stamp moves from a bare integer to `major.minor`:

- **Major bump** — breaking changes (renamed/removed fields, type changes, semantic changes). Old consumers refuse.
- **Minor bump** — additive (new optional field). Old consumers ignore the new field and keep working.

Consumers declare a supported range (e.g. `>=1.0, <2.0`) and check the stamp on every read, the way `snapshot.read()` does today. A snapshot stamped `1.5` is fine; `2.0` is not.

Initial release ships at `1.0`.

## Consumer contract

- Each consumer **vendors `schema/snapshot.schema.json`** from a known exporter release (committed copy) and pins the supported version range.
- The Go CLI uses **hand-written structs and a version check** on read, mirroring `snapshot.read()` in Python. No runtime JSON Schema validation; no codegen step in the Go build.
- The future UI follows the same model — hand-written types, version check, schema vendored.
- Each consumer reimplements the grouping/summary it needs. The daily-row shape is small; centralising a parsing/aggregation lib is not worth the cross-repo coupling.

## Release flow when bumping schema

1. PR on `mt5-pnl-exporter`: change models, bump version (in both `SCHEMA_VERSION` and the regenerated schema file), tag a release.
2. PR on each consumer that needs the new shape: widen the supported range, handle the new field. Release independently.
3. Old CLI/UI binaries keep working against old snapshots — and against new ones too if the bump was minor.

## Phased implementation

Strict sequence. Each phase lands stable before the next starts.

This doc is the architectural decomposition, not a single implementation plan. **Each phase begins with its own superpowers cycle** — `brainstorming` to produce a per-phase spec, then `writing-plans` to produce the implementation plan, then execution. The bullet points under each phase below are the design contract that constrains those per-phase brainstorms; they are not the plan itself. Re-brainstorming per phase is deliberate: each phase will have learned things from the previous one that should shape the brief.

### Phase 1 — Stand up `mt5-pnl-exporter`

Split into two sub-phases so that planned exporter simplifications land before the schema version is publicly committed. Tagging `1.0` then `2.0` in quick succession with no consumer in between would churn the version for nothing.

**Phase 1a — Port**

- Create new GitHub repo `mt5-pnl-exporter`.
- Port from the current repo: `poll` and `set-password` commands; `sources/` (base, mt5, fixture); `snapshot.py`; `secrets.py`; the poll-side bits of `config.py`; the tests covering these.
- Drop the query commands (`pnl`, `accounts`) and the query-side config (`account_groups`, `staleness_warn_hours`) entirely — they belong in the Go CLI.
- Add `schema/snapshot.schema.json` (generated from pydantic). Add the generator command and a CI staleness check.
- Release as `0.x` — pre-release, no schema-version commitment yet.

**Phase 1b — Simplify and tag `1.0`**

Each discrete simplification gets its own superpowers cycle (brainstorm → spec → plan → execute) rather than one mega-spec. The bullets below constrain those cycles.

- Land the planned exporter simplifications in the new repo.
- Adopt the `major.minor` version policy. Tag `1.0` only when the schema is what you want to commit to long-term.
- Publish to PyPI as `mt5-pnl-exporter` with the `[mt5]` optional dep group.
- README documents `uv tool install "mt5-pnl-exporter[mt5]"`.

### Phase 2 — Stand up `mt5-pnl-cli`

Re-enter the superpowers cycle (brainstorm → spec → plan → execute) at the start of this phase, when Phase 1 has shipped and the schema, config shape, and flag semantics are known precisely. The bullets below are the design contract that constrains that brainstorm.

- Create new GitHub repo `mt5-pnl-cli`. Go module.
- Vendor `schema/snapshot.schema.json` from the `mt5-pnl-exporter` 1.0 release.
- Hand-write structs matching the schema; version check on read; refuse unsupported versions.
- Reimplement `pnl` and `accounts` commands in Go, preserving the existing flags (`--last`, `--group`, `--group-name`, `--json`).
- Reimplement YAML loading of `account_groups`.
- Cross-compile binaries for Windows/macOS/Linux; ship via GitHub Releases.
- Once at parity, document as the canonical query tool.

### Phase 3 — Delete `mt5-pnl`

- Once `mt5-pnl-exporter` is on PyPI and Go CLI binaries exist and have been smoke-tested against a real snapshot, delete the current `mt5-pnl` repo.

### Phase 4 — `mt5-pnl-ui` (deferred)

Re-enter the superpowers cycle when there's appetite to build a UI — too far away to plan meaningfully now.

- Tech stack decided then. Same contract as the Go CLI: vendor the schema, version check, reimplement aggregation.

## Out of scope (deliberately)

- **No `mt5-pnl-schema` repo.** Schema lives in the exporter. Extract later if a second producer ever appears (it won't — MT5 ships no other binding).
- **No consumer-side parsing/aggregation library.** Each consumer rolls its own. Daily-row shape is small enough that cross-repo coupling cost outweighs the duplication saved.
- **No `--schema-version=N` migration-window flag.** The exporter only writes the current version. With both consumers under one owner, bumps can be coordinated without a flag. Add it the first time a real bump causes pain.
- **No PyInstaller / Nuitka bundle for the exporter.** `uv tool install` is the install story. Revisit if a "no Python at all" install ever becomes a real ask.
- **No UI tech decision yet.** Defer to Phase 4.

## Reference architectures

Patterns this design borrows from:

- **`compile_commands.json`** (clang) — build systems write it, clangd / clang-tidy / IDE plugins all read it. One JSON schema replaced N×M tool/build-system integrations with N+M.
- **SARIF** — OASIS-standardised JSON for static-analysis results. Linters produce it (`--format sarif`); GitHub Code Scanning, Azure DevOps, VS Code's SARIF Viewer all render it. Versioned (2.1.0); consumers check and adapt — same pattern as `snapshot.read()`.
- **Prometheus exposition format / OTLP** — wire formats as the contract. Exporters write them, many backends read them. Producer and consumer share no runtime — they share a documented, versioned format.
- **SQLite as an application file format** and the Parquet/DuckDB workflow — same "file is the API" pattern at different scales.
