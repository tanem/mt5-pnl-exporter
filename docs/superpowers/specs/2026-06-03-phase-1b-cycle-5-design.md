# Phase 1b cycle 5: pre-publish docs polish

Status: design. Ready to plan implementation once approved.

Refines the "Next: cycle 5" subsection of
[`2026-06-02-phase-1b-cycle-4-design.md`](2026-06-02-phase-1b-cycle-4-design.md).
Lands the docs polish that gates the `1.0.0` git tag and the first
`uv publish`. Code-free PR: only `.md` files plus minor `CLAUDE.md`
wording sweeps. A small follow-on cycle 6 wires codecov before the tag;
the trusted-publish workflow and `pyproject` classifiers stay in the
post-publish follow-up.

## Why

Cycle 4 landed the version policy and the `1.0.0` package metadata, but
the README still reads as a working-notes file from the 0.x days. The
top of the file lacks badges, a tagline, an elevator-pitch visual, or a
sample of what the tool actually produces — exactly the things a first-
time visitor uses to decide "is this for me" within thirty seconds. The
existing `## Status` paragraph still says "0.x — pre-release ... Tag
`1.0` ships once the planned simplifications have landed", which will
be untrue the moment the tag exists.

The repo also lacks `CONTRIBUTING.md` and `SECURITY.md`, both of which
`mt5-pnl` has and both of which are conventional pre-publish hygiene
for a public Python package.

Cycle 5 closes those gaps in one docs-only PR so cycle 6 can stay
narrowly scoped to codecov and the tag can ship against a presentable
README.

## Deliverables

Four deliverables, all `.md` files, all in one PR.

1. **README rewrite** — full reorder around art-of-readme principles,
   new tagline, badges, two ASCII diagrams, Quick start showing a
   terminal session and the decrypted snapshot shape. `## Status`
   removed.
2. **CLAUDE.md polish** — strip the now-stale "Tag `1.0` ships once
   the planned simplifications have landed" framing; add a one-line
   reminder near the `snapshot.py` architecture line that schema-model
   edits must regenerate `schema/snapshot.schema.json`.
3. **New CONTRIBUTING.md** — ported from `mt5-pnl/CONTRIBUTING.md`,
   adjusted for the exporter surface.
4. **New SECURITY.md** — ported from `mt5-pnl/SECURITY.md`, adjusted
   to cover both the investor passwords and the encryption passphrase.

A fifth deliverable, the design-doc hygiene edit to the cycle 4 spec,
is described under "Design-doc hygiene" below — a two-line change to
the sequence diagram, not a separate file.

## README restructure

### Final section order

```
# mt5-pnl-exporter
[badges row]
> tagline (blockquote)
[family-of-tools diagram]
intro paragraph

## Contents
[TOC]

## Why
- bullets

## Install
[unchanged]

## Quick start
[terminal session + decrypted snapshot shape]

## Commands
[unchanged]

## Configuration
[unchanged]

## How it works
[pipeline diagram + two-paragraph explanation]

## Schema
[unchanged content; cycle 4's major.minor paragraph stays]

## Snapshot size
[unchanged]

## Threat model
[unchanged, retain the three subsections]

## Contributing
short pointer to CONTRIBUTING.md

## Licence
MIT — see LICENSE.
```

The existing `## Status` section is removed. The PyPI version badge in
the badge row and the major.minor paragraph in `## Schema` together
carry the stability messaging without a dedicated section.

### Badges

Four badges. Licence / Python / tests carry over from `mt5-pnl`; PyPI
is new (mt5-pnl is git-only); coverage waits for cycle 6.

- Licence — `shields.io/github/license/tanem/mt5-pnl-exporter`
- Python 3.12+ — static badge
- tests — `github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg`
- PyPI version — `shields.io/pypi/v/mt5-pnl-exporter` (renders empty
  until the tag/publish sequence completes; no edit needed afterwards)

### Tagline and intro

Contract-first framing — leads with what consumers receive, then what
runs where:

> A stable, typed, encrypted snapshot of your MT5 deal history. Build
> a CLI, a dashboard, a notebook, or an AI agent on top — the snapshot
> is the contract.

One paragraph beneath the family diagram:

> Runs on the Windows host where MT5 lives, reads deal history with a
> read-only investor password, writes one encrypted file. No daemon,
> no database, no third-party service.

### Family-of-tools diagram (top of file)

Sits between the tagline and the intro paragraph. Shows the exporter's
position in the wider mt5-pnl tool family:

```
   ┌──────────────┐  writes   ┌────────────────┐  reads   ┌──────────────┐
   │ mt5-pnl-     │ ────────► │ snapshot.json  │ ───────► │ mt5-pnl-cli  │
   │ exporter     │           │ .gz.age        │          │ mt5-pnl-ui   │
   │ (this repo)  │           │ (the contract) │          │ your tools   │
   └──────┬───────┘           └────────────────┘          └──────────────┘
          ▲ MT5 deal history
   ┌──────┴───────┐
   │ Windows host │
   └──────────────┘
```

### Why (bulleted)

```
- **Self-hosted.** No myfxbook, no fxblue, no third party holds your
  trading data. Runs on a Windows host you control.
- **Stable contract.** One typed, versioned snapshot — build whatever
  frontend suits you. Schema follows `major.minor`; minor bumps add
  optional fields, major bumps are breaking.
- **Read-only credentials.** Investor passwords can view balances and
  trade history but can never place or modify a trade.
- **Encrypted at rest.** Snapshot is gzipped then `age`-encrypted under
  a passphrase from the OS keychain. Safe to sync via Dropbox,
  OneDrive, or Syncthing.
```

### Quick start (terminal session + snapshot shape)

```bash
$ mt5-pnl-exporter set-password 1234567
Password stored in keychain for login 1234567.

$ mt5-pnl-exporter set-encryption-passphrase
Encryption passphrase stored in keychain.

$ cp config.example.yaml config.yaml && chmod 600 config.yaml
# edit config.yaml — snapshot_path, terminal_path, accounts

$ mt5-pnl-exporter poll
[poll] Trend EA (1234567): 12 closed deals, 0 open, 0 cash flows  OK
[poll] Scalper EA (7654321): 8 closed deals, 1 open, 2 cash flows  OK
[poll] wrote ~/snapshots/mt5.json.gz.age  (2026-06-03 12:00)
```

Followed by:

> After decrypt + gunzip, the snapshot looks like:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-03T12:00:00Z",
  "accounts":         [{"login": 1234567, "label": "Trend EA", "currency": "USD", "balance": 10240.50, "equity": 10198.20, "last_success": "2026-06-03T12:00:00Z", "last_error": null}],
  "closed_deals":     [{"account": 1234567, "ticket": 9876543, "time": "2026-06-02T14:31:22Z", "symbol": "EURUSD", "type": "buy", "volume": 0.10, "price": 1.0834, "profit": 12.40, "swap": 0.0, "commission": -0.70, "fee": 0.0}],
  "open_positions":   [],
  "cash_flows":       []
}
```

The `[poll]` log format matches what `cli.py:113-117` and `cli.py:151`
currently emit; example field values for `closed_deals` / `accounts`
are illustrative, matching the pydantic model shapes in `snapshot.py`.
During plan-writing, verify exact field names against the current
models (this avoids drift if any field was renamed since cycle 4).

### How it works section

A new H2 between `## Configuration` and `## Schema`. Two short paragraphs
plus the pipeline diagram:

```
deals (live)    ──► Snapshot    ──► gzip      ──► age encrypt ──► snapshot.json.gz.age
MT5 terminal       pydantic         (~10× smaller)  passphrase     (atomic .tmp swap)
                   models                            from keychain
```

Paragraph 1: `poll` runs where MT5 lives; logs in with the investor
password; reads closed deals, open positions, balance-family deals via
the MT5 Python API; writes one encrypted snapshot file. The full
history is rebuilt each run — idempotent, so missed runs auto-backfill.

Paragraph 2: gzip + `age` encryption is mandatory, not optional. The
on-disk file is always `snapshot.json.gz.age`; readers must reverse the
pipeline to decrypt. Sync services (Dropbox, OneDrive, Syncthing) and
backups only ever see ciphertext.

### Sections that stay (largely) unchanged

`## Install`, `## Commands`, `## Configuration`, `## Schema`,
`## Snapshot size`, `## Threat model` — content stays. Edits limited
to:

- Cross-references updated (e.g. "see `## Status`" → removed).
- Minor wording polish for NZ English consistency where caught.
- `## Threat model` keeps its three subsections (What's protected /
  What's not protected / Transport guidance).

### Contents (TOC)

Mirrors `mt5-pnl`'s style — bulleted list of anchor links under a
`## Contents` H2, sitting between the family diagram and `## Why`.
Manually maintained. Includes every H2 below it.

## CLAUDE.md polish

Two edits, both small:

1. **Strip the stale 1.0 framing.** Any line that still reads "Tag
   `1.0` ships in Phase 1b once …" or equivalent — replace with the
   current state of affairs (the package is at `1.0.0`, the schema
   stamp is `"1.0"`, the next milestone is the manual tag/publish
   after cycle 6).
2. **Add the schema-regen reminder.** Near the existing `snapshot.py`
   architecture line, add: "After editing `Snapshot` / nested models,
   run `uv run mt5-pnl-exporter schema` and commit the regenerated
   `schema/snapshot.schema.json` — `tests/test_schema_file.py` will
   otherwise fail."

No architectural change. Verify the exact CLAUDE.md state during
plan-writing and adjust the patch to match.

## CONTRIBUTING.md (new file)

Port from `mt5-pnl/CONTRIBUTING.md`. Adjustments:

- Replace `mt5pnl` → `mt5-pnl-exporter` throughout (including the
  `src/mt5pnl` → `src/mt5_pnl_exporter` mypy path).
- Drop the "Developing without MT5" section — the exporter has no
  `FixtureSource` and no `--source fixture` flag.
- Drop the `pnl` command example.
- Add a "Regenerating the schema" subsection covering the
  `uv run mt5-pnl-exporter schema` flow (same content as the new
  CLAUDE.md reminder, framed for contributors rather than maintainers).
- Keep the "Never import `MetaTrader5` at module level" convention —
  still applies (the `schema` command works on any OS precisely
  because of this).
- Keep NZ English and the "update README + CLAUDE.md together" rule.

Target length similar to mt5-pnl's (~35 lines).

## SECURITY.md (new file)

Port from `mt5-pnl/SECURITY.md`. Adjustments:

- **Scope paragraph** — cover both the read-only investor passwords
  *and* the snapshot encryption passphrase. Both live only in the OS
  keychain on the Windows host; neither is written to disk or logs.
- **In-scope items** — add: "Snapshot encryption pipeline (gzip +
  `age`) bypassed, weakened, or producing files readable without the
  passphrase."
- **Out-of-scope items** — drop the ForexVPS reference (irrelevant
  here); keep MT5 server / broker infrastructure.
- **Reporting URL** — `tanem/mt5-pnl-exporter/security/advisories/new`.
- Keep the 7-day response commitment and the disclosure-coordination
  language.

Target length similar to mt5-pnl's (~29 lines).

## Markdown render check

Per the standing preference (memory entry: "Markdown render check"),
after non-trivial `.md` edits run `gh api /markdown` in gfm + repo
context against each edited file. Cycle 5 touches four files
(README.md, CLAUDE.md, CONTRIBUTING.md, SECURITY.md), so this is four
render passes — once per file after its content settles.

Flag any visual-only issues (notably ASCII diagram alignment under
GitHub's proportional code font, which can subtly mis-align box-drawing
characters compared to a monospace local render) for human review
before the PR opens.

## Design-doc hygiene

The cycle 4 spec's "Sequence" diagram under "Next: cycle 5" currently
shows:

```
Cycle 4 PR ──► Cycle 5 PR ──► manual tag/publish ──► follow-up PR
```

This becomes incorrect once cycle 6 exists. Add a two-edit pass to
`2026-06-02-phase-1b-cycle-4-design.md` in the same PR:

1. Replace the sequence diagram with the cycle-6-aware version (see
   "Post-merge sequence" below).
2. Update the "Tag and publish (after cycle 5 merges)" heading to
   "Tag and publish (after cycle 6 merges)" and the matching prose.

No other edits to the cycle 4 spec — its content is still correct.

## Branching and PR

Branch `phase-1b-cycle-5` from `main` (currently `24fa811`, the
cycle 4 merge). No direct pushes to `main`. PR is **regular** (not
draft) — opens ready for review immediately, per the standing
preference.

Plan ends with: commit straggling changes → push branch → open PR.

## Post-merge sequence

```
Cycle 5 PR (this)  : pre-publish docs polish
        ↓ merge
Cycle 6 PR         : codecov upload step + coverage badge
        ↓ merge
manual             : git tag 1.0.0 && git push --tags
        ↓
manual             : uv build && uv publish
        ↓
Follow-up PR       : GHA trusted-publish workflow + pyproject
                     classifiers / urls / inline license
```

Cycle 6 is small enough to brainstorm inline rather than its own
design doc — likely scope: add `codecov/codecov-action@v5` step to
`ci.yml` using `CODECOV_TOKEN`, add coverage badge to the README badge
row, no other changes. Treat the scope as confirmed when this spec
is approved; defer the implementation details to cycle 6's plan.

If cycle 6 slips, the tag and the publish wait too.

## Out of scope (deferred to cycle 6 or to the post-publish follow-up)

- **Codecov upload step and coverage badge** — cycle 6, before the tag.
- **GHA trusted-publish workflow** — post-publish follow-up PR (needs
  the project to exist on PyPI to configure the trusted publisher).
- **`pyproject` metadata polish** — inline `license = "MIT"`,
  `[project.urls]` table, `classifiers = [...]` — post-publish follow-
  up, alongside the trusted-publish workflow.
- **Asciinema recording / screenshots** — static code blocks in the
  README do the job; recording adds production cost without obvious
  return.
- **Code changes of any kind** — cycle 5 is `.md`-only. Any code drift
  noticed during the docs sweep gets noted for a subsequent cycle, not
  patched here.
