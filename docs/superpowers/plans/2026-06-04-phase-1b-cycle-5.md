# Phase 1b cycle 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the pre-publish docs polish — README rewrite to art-of-readme structure, new `CONTRIBUTING.md` and `SECURITY.md`, plus a small `CLAUDE.md` audit and a design-doc-hygiene edit to the cycle 4 spec.

**Architecture:** Docs-only PR on branch `phase-1b-cycle-5` (already created, head: `de99dcb` — the spec commit). Each task touches one file, ends with a render check and a commit. README write is the largest single task; the rest are small and isolated.

**Tech Stack:** Markdown. Verification via `gh api /markdown` (gfm + repo context). Final sanity check via existing `ruff` / `mypy` / `pytest` (should be unchanged — no code touched).

---

## Files

- **Modify:** `CLAUDE.md` — audit only; edit if stale wording found.
- **Modify:** `docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md` — sequence diagram + one heading.
- **Create:** `SECURITY.md` — vuln-reporting policy, ported from `mt5-pnl` repo with passphrase-aware scope.
- **Create:** `CONTRIBUTING.md` — contributor setup + conventions, ported from `mt5-pnl` repo with exporter-specific adjustments.
- **Modify:** `README.md` — full rewrite to art-of-readme structure.

Order of work: smallest/most-isolated first; README last because it's the largest and reviewers will want fresh eyes on it.

---

### Task 1: CLAUDE.md audit and (only-if-needed) edit

**Files:**
- Modify (conditional): `/Users/tane/Code/mt5-pnl-exporter/CLAUDE.md`

The spec called for stripping stale "Tag `1.0` ships once …" framing and adding a schema-regen reminder near the `snapshot.py` line. A 2026-06-04 audit found neither edit was needed — the stale phrase isn't present, and a schema-regen Gotcha already exists (line 40: "**Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`."). This task re-verifies at execution time and only edits if anything new has drifted in.

- [ ] **Step 1: Read the current CLAUDE.md**

Use the Read tool on `/Users/tane/Code/mt5-pnl-exporter/CLAUDE.md`.

- [ ] **Step 2: Audit for stale 1.0 framing**

Search the file content for any of:
- "Tag `1.0` ships"
- "pre-release"
- "0.x"
- "once the planned simplifications have landed"

Expected: none of these are present. If any are, capture the offending line and proceed to step 3. If none are, skip to step 5.

- [ ] **Step 3: Audit for missing schema-regen reminder**

Confirm the Gotchas section contains a line equivalent to: "Regenerate the schema after model changes: `uv run mt5-pnl-exporter schema`."

Expected: present at the existing line position. If missing, proceed to step 4. If present, skip to step 5.

- [ ] **Step 4: Edit only if step 2 or step 3 found a gap**

If step 2 found stale wording, remove it (replace with current-state wording: `SCHEMA_VERSION` is `"1.0"`, next milestone is the manual tag/publish after cycle 6).

If step 3 found the schema-regen reminder missing, add this exact bullet to the Gotchas list, immediately before the `SCHEMA_VERSION is "1.0"` line:

```markdown
- **Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`. `tests/test_schema_file.py` catches missed regenerations.
```

- [ ] **Step 5: If no edit was made, document the no-op in the commit log of Task 6**

Skip to Task 2. Record under Task 6's wrap-up: "CLAUDE.md audit: no stale references; no edit needed."

- [ ] **Step 6: If an edit was made, render check then commit**

Run:

```bash
gh api /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter -F text=@CLAUDE.md > /tmp/claude-md-rendered.html
```

Expected: HTML output produced, exit 0. Open `/tmp/claude-md-rendered.html` in a browser and visually verify formatting; flag visual issues if any. Then:

```bash
git -C /Users/tane/Code/mt5-pnl-exporter add CLAUDE.md
git -C /Users/tane/Code/mt5-pnl-exporter commit -m "docs(claude.md): polish stale 1.0 references"
```

---

### Task 2: Design-doc hygiene — update cycle 4 spec's sequence diagram

**Files:**
- Modify: `/Users/tane/Code/mt5-pnl-exporter/docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md`

The cycle 4 spec's "Next: cycle 5" subsection contains a sequence diagram that does not anticipate cycle 6. Update it.

- [ ] **Step 1: Read the cycle 4 spec, locate the sequence diagram**

Use Read on `/Users/tane/Code/mt5-pnl-exporter/docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md`. The diagram is in the "Next: cycle 5 (pre-publish docs polish)" subsection (around line 205).

Current content:

```
Cycle 4 PR (this)  : version policy + code + minimal pyproject
        ↓ merge
Cycle 5 PR         : pre-publish README/docs polish (scope TBD)
        ↓ merge
manual             : git tag 1.0.0 && uv publish
        ↓
Follow-up PR       : GHA trusted-publish workflow + pyproject metadata
```

- [ ] **Step 2: Replace the sequence diagram**

Use the Edit tool to replace the block above with:

```
Cycle 4 PR         : version policy + code + minimal pyproject  ✓ merged
        ↓
Cycle 5 PR         : pre-publish README/docs polish
        ↓ merge
Cycle 6 PR         : codecov upload step + coverage badge
        ↓ merge
manual             : git tag 1.0.0 && git push --tags
        ↓
manual             : uv build && uv publish
        ↓
Follow-up PR       : GHA trusted-publish workflow + pyproject metadata
```

- [ ] **Step 3: Update the "Tag and publish" heading + its lead-in sentence**

Find the H2: `## Tag and publish (after cycle 5 merges)` and change to `## Tag and publish (after cycle 6 merges)`.

The opening sentence beneath the heading currently reads "Once both cycle 4 and cycle 5 are on `main`:" — change to "Once cycle 4, cycle 5, and cycle 6 are all on `main`:".

- [ ] **Step 4: Render check**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh api /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter \
  -F text=@docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md \
  > /tmp/cycle-4-spec-rendered.html
```

Expected: HTML output produced, exit 0. Visually verify the sequence diagram still renders cleanly inside its code block.

- [ ] **Step 5: Commit**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter add docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md
git -C /Users/tane/Code/mt5-pnl-exporter commit -m "docs(spec): update cycle 4 sequence diagram to include cycle 6"
```

---

### Task 3: Write SECURITY.md

**Files:**
- Create: `/Users/tane/Code/mt5-pnl-exporter/SECURITY.md`

Ported from `mt5-pnl/SECURITY.md` with adjustments for the exporter:
- Scope mentions both investor passwords *and* the encryption passphrase.
- In-scope adds an item for the encryption pipeline.
- Out-of-scope drops the ForexVPS reference; keeps MT5/broker.
- Reporting URL points at this repo.

- [ ] **Step 1: Create the file with this content**

Use the Write tool on `/Users/tane/Code/mt5-pnl-exporter/SECURITY.md` with this exact content:

````markdown
# Security policy

## Scope

This tool handles **read-only MT5 investor passwords** — credentials that can view account data but cannot place or modify trades — and a **snapshot encryption passphrase** used to age-encrypt the on-disk snapshot. Both live only on the Windows host where `poll` runs, in its OS keychain via `keyring` (Windows Credential Manager). Neither is written to disk, logs, or the snapshot file.

Vulnerabilities in scope:

- Secrets disclosure (investor passwords, the encryption passphrase, account numbers, or balances leaking in logs, the snapshot, or any other output)
- Unsafe keychain read/write behaviour
- Snapshot encryption pipeline (gzip + `age`) bypassed, weakened, or producing files readable without the passphrase
- Snapshot written in a way that allows partial reads or unauthorised access by other local users
- Dependency vulnerabilities with a plausible exploitation path in this tool

Out of scope:

- MT5 server or broker infrastructure (not under this project's control)
- Issues only reproducible with a non-current Python or uv version

## Reporting

**Do not open a public GitHub issue for security vulnerabilities.** Public issues expose the vulnerability before a fix is available.

Report privately via the Security tab — [Report a vulnerability](https://github.com/tanem/mt5-pnl-exporter/security/advisories/new). This opens a private workspace visible only to you and the maintainer.

> [!NOTE]
> **For the maintainer:** enable *Settings → Code security → Private vulnerability reporting* so the "Report a vulnerability" button appears.

You will receive a response within 7 days. Once a fix is ready, we will coordinate a disclosure timeline with you before publishing.
````

- [ ] **Step 2: Render check**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh api /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter \
  -F text=@SECURITY.md > /tmp/security-md-rendered.html
```

Expected: HTML output produced, exit 0. Verify the GFM `> [!NOTE]` callout renders as a styled note block.

- [ ] **Step 3: Commit**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter add SECURITY.md
git -C /Users/tane/Code/mt5-pnl-exporter commit -m "docs: add SECURITY.md (vuln-reporting policy)"
```

---

### Task 4: Write CONTRIBUTING.md

**Files:**
- Create: `/Users/tane/Code/mt5-pnl-exporter/CONTRIBUTING.md`

Ported from `mt5-pnl/CONTRIBUTING.md` with exporter-specific adjustments:
- `mt5pnl` → `mt5-pnl-exporter` throughout (including the mypy package path).
- Drops the "Developing without MT5" / `FixtureSource` / `pnl` material.
- Adds a "Regenerating the schema" subsection.
- Keeps the "Never import `MetaTrader5` at module level" convention.

- [ ] **Step 1: Create the file with this content**

Use the Write tool on `/Users/tane/Code/mt5-pnl-exporter/CONTRIBUTING.md` with this exact content (outer fence uses 4 backticks so the inner `bash` blocks render correctly):

`````markdown
# Contributing

Thanks for your interest. This is a small project — issues and PRs are welcome.

## One-time setup

```bash
uv sync                              # install dependencies
uv run pre-commit install            # enable the gitleaks secret-scan hook
```

## Running tests and hooks

```bash
uv run pytest                        # run the test suite (coverage gate: ≥95%)
uv run pre-commit run --all-files    # run the gitleaks hook manually
uv run ruff check src/ tests/        # lint
uv run ruff format --check src/ tests/  # check formatting
uv run mypy src/mt5_pnl_exporter     # type-check
```

## Regenerating the schema

After editing the `Snapshot` model or any of its nested models in `snapshot.py`, regenerate `schema/snapshot.schema.json`:

```bash
uv run mt5-pnl-exporter schema
```

`tests/test_schema_file.py` fails CI if the committed schema drifts from the model. Commit the regenerated file alongside the model change.

## Conventions

- NZ English in comments and docs (realise, behaviour, colour).
- Never import `MetaTrader5` at module level. Keep it deferred inside `MT5Source` (`sources/mt5.py`) so commands like `schema` work on machines without the `MetaTrader5` package installed.
- Tests use a fake `DataSource` injected in place of `MT5Source` — never mock the `MetaTrader5` package directly.
- After changing commands, architecture, or gotchas, update both `README.md` and `CLAUDE.md` in the same change.
`````

- [ ] **Step 2: Render check**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh api /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter \
  -F text=@CONTRIBUTING.md > /tmp/contributing-md-rendered.html
```

Expected: HTML output produced, exit 0. Verify the three `bash` code blocks each render as fenced code (not flowed prose).

- [ ] **Step 3: Commit**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter add CONTRIBUTING.md
git -C /Users/tane/Code/mt5-pnl-exporter commit -m "docs: add CONTRIBUTING.md (setup + conventions)"
```

---

### Task 5: Rewrite README.md

**Files:**
- Modify: `/Users/tane/Code/mt5-pnl-exporter/README.md` (full replacement)

The largest task. Replaces the current 104-line README with the art-of-readme-structured version. Section order: title/badges/tagline/family diagram/intro → Contents → Why → Install → Quick start → Commands → Configuration → How it works → Schema → Snapshot size → Threat model → Contributing → Licence.

- [ ] **Step 1: Read the current README**

Use Read on `/Users/tane/Code/mt5-pnl-exporter/README.md`. The unchanged sections (Schema, Snapshot size, Threat model) need their content carried over verbatim — confirm by reading.

- [ ] **Step 2: Write the new README**

Use the Write tool on `/Users/tane/Code/mt5-pnl-exporter/README.md` with this exact content:

`````markdown
# mt5-pnl-exporter

[![Licence](https://img.shields.io/github/license/tanem/mt5-pnl-exporter)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![tests](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mt5-pnl-exporter)](https://pypi.org/project/mt5-pnl-exporter/)

> A stable, typed, encrypted snapshot of your MT5 deal history. Build a CLI, a dashboard, a notebook, or an AI agent on top — the snapshot is the contract.

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

Runs on the Windows host where MT5 lives, reads deal history with a read-only investor password, writes one encrypted file. No daemon, no database, no third-party service.

## Contents

- [Why](#why)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Schema](#schema)
- [Snapshot size](#snapshot-size)
- [Threat model](#threat-model)
- [Contributing](#contributing)
- [Licence](#licence)

## Why

- **Self-hosted.** No myfxbook, no fxblue, no third party holds your trading data. Runs on a Windows host you control.
- **Stable contract.** One typed, versioned snapshot — build whatever frontend suits you. Schema follows `major.minor`; minor bumps add optional fields, major bumps are breaking.
- **Read-only credentials.** Investor passwords can view balances and trade history but can never place or modify a trade.
- **Encrypted at rest.** Snapshot is gzipped then `age`-encrypted under a passphrase from the OS keychain. Safe to sync via Dropbox, OneDrive, or Syncthing.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Quick start

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
[poll] wrote ~/snapshots/mt5.json.gz.age  (2026-06-04 12:00)
```

After decrypt + gunzip, the snapshot looks like:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-04T12:00:00Z",
  "accounts": [
    {
      "login": 1234567,
      "label": "Trend EA",
      "currency": "USD",
      "balance": 10240.50,
      "equity": 10198.20,
      "last_success": "2026-06-04T12:00:00Z",
      "last_error": null
    }
  ],
  "closed_deals": [
    {
      "account": 1234567,
      "ticket": 9876543,
      "time": 1748867482,
      "symbol": "EURUSD",
      "type": 0,
      "entry": 1,
      "volume": 0.10,
      "price": 1.0834,
      "profit": 12.40,
      "swap": 0.0,
      "commission": -0.70,
      "fee": 0.0
    }
  ],
  "open_positions": [],
  "cash_flows": []
}
```

`ClosedDeal` and `OpenPosition` carry every field MT5 emits — raw `type` and `entry` integers, `time` as Unix seconds, etc. See [`schema/snapshot.schema.json`](schema/snapshot.schema.json) for the full shape.

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json.gz.age` atomically.
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain (`keyring`).
- `mt5-pnl-exporter set-encryption-passphrase` — store the snapshot encryption passphrase in the OS keychain (entered twice).
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic `Snapshot` model.

## Configuration

Copy `config.example.yaml` to `config.yaml` (gitignored) and fill in your values:

```yaml
snapshot_path: ~/snapshots/mt5.json.gz.age
terminal_path: C:\mt5-poller\terminal64.exe
accounts:
  - label: Trend EA
    login: 1234567
    server: BrokerName-Live
  - label: Scalper EA
    login: 7654321
    server: BrokerName-Live
```

Run `chmod 600 config.yaml` — `poll` refuses to run otherwise. Investor passwords and the encryption passphrase go in the OS keychain via `set-password` and `set-encryption-passphrase`, never in this file.

## How it works

```
deals (live)    ──► Snapshot    ──► gzip      ──► age encrypt ──► snapshot.json.gz.age
MT5 terminal       pydantic         (~10× smaller)  passphrase     (atomic .tmp swap)
                   models                            from keychain
```

`poll` logs into each account with its investor password, reads closed deals, open positions, and balance-family deals via the `MetaTrader5` Python API, then assembles them into a typed `Snapshot`. The full history is rebuilt each run — idempotent, so a missed run auto-backfills on the next tick.

Gzip + `age` encryption is mandatory, not optional. The on-disk file is always `snapshot.json.gz.age`; readers must reverse the pipeline (`age decrypt → gunzip → json.loads`) to decrypt. Sync services (Dropbox, OneDrive, Syncthing) and backups only ever see ciphertext.

## Schema

`schema/snapshot.schema.json` is generated from the pydantic models and committed. CI (`tests/test_schema_file.py`) fails if it drifts. Consumers vendor the file from a specific release. The on-disk file is the schema's JSON gzipped then encrypted with [age](https://age-encryption.org/) under a passphrase from the OS keychain — consumers must reverse the same pipeline to read it.

The snapshot carries one record per closed deal (`ClosedDeal`), open position (`OpenPosition`), and balance-family deal — deposit, withdrawal, credit, charge, correction, bonus, commission (`CashFlow`). Plus one `AccountSnapshot` per account with balance, equity, currency, and the last-success/last-error stamps. No pre-aggregation — consumers slice the raw records however they want.

Schema version stamping is `major.minor` (`SCHEMA_VERSION = "1.0"`). Readers accept the same major and any minor ≤ their own; minor bumps add optional fields, major bumps are breaking. Consumers vendor `schema/snapshot.schema.json` from a specific release.

## Snapshot size

The snapshot stores one record per closed deal, so it grows with trading volume. Rough sizing: ~350 bytes per closed-deal record. Ten accounts with two years of 50-deals-per-day-per-account history (~250 trading days/year) is around 90 MB; busier setups (200 deals/day) reach ~350 MB. Each `poll` gzips the JSON before encrypting, so the on-disk file is roughly an order of magnitude smaller — the 350 MB worst case lands at ~35 MB on disk, which is what sync services (Dropbox, Syncthing) see.

## Threat model

The OS user account on the Windows host that runs the exporter is the trust boundary. Anyone with that account's session can read the keychain, run `poll`, and read decrypted snapshots. The same applies to a consumer machine: anyone with that account's session can decrypt the snapshot. The exporter does not defend against a compromised user session on either side.

### What's protected

- **Snapshot contents at rest off the Windows host.** Sync services (Dropbox, OneDrive, Syncthing), backups, and transit only ever see the gzipped, age-encrypted file. Mandatory encryption is what gets you this.
- **Investor passwords and the encryption passphrase, on disk and in logs.** Stored only in the OS keychain. The `redact_filter` strips any registered secret from log lines.

### What's not protected

- **A compromised user session on either host.** With keychain access the snapshot decrypts to plaintext.
- **Traffic-analysis metadata.** File size, sync timing, and whether a poll ran today are visible to anyone observing the transport. age hides contents, not existence.
- **Passphrase loss.** There is no recovery. The snapshot is reproducible, though — re-run `poll` to rebuild it from the broker's history.
- **The broker side.** MT5 deal history lives on the broker's server and is governed by their controls, not by anything in this tool.

### Transport guidance

Once the file is encrypted at rest, transport choice carries less weight than it used to. scp/rsync over SSH, a synced folder (Dropbox/Syncthing/OneDrive), or reading on the same machine are all viable. Pick whichever fits the workflow.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). For security reports, see [SECURITY.md](SECURITY.md).

## Licence

MIT — see [LICENSE](LICENSE).
`````

- [ ] **Step 3: Visually verify the two ASCII diagrams locally**

Open `/Users/tane/Code/mt5-pnl-exporter/README.md` in any monospace viewer. Confirm:
- The family-of-tools diagram (top) has the three boxes aligned, the `▲` and `┴` connectors line up, and "Windows host" sits directly under "mt5-pnl-exporter".
- The pipeline diagram (in How it works) has the arrows in line and the second/third lines do not overflow.

If any visual issue, fix the spacing in the README (small character-by-character adjustments) and re-verify.

- [ ] **Step 4: Render check against GitHub**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh api /markdown -f mode=gfm -f context=tanem/mt5-pnl-exporter \
  -F text=@README.md > /tmp/readme-rendered.html
```

Expected: HTML output produced, exit 0. Open `/tmp/readme-rendered.html` in a browser and verify:
- Badge images render (or at least the alt text appears as links if shields.io is blocked).
- The blockquote tagline renders correctly.
- Both ASCII diagrams sit inside `<pre>` blocks and stay monospace-aligned.
- The `## Contents` anchors all link to their target H2s.
- The Quick start `bash` and `json` blocks each get syntax highlighting.

Flag any visual issues for human review before proceeding.

- [ ] **Step 5: Commit**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter add README.md
git -C /Users/tane/Code/mt5-pnl-exporter commit -m "docs(readme): rewrite to art-of-readme structure for 1.0"
```

---

### Task 6: Final sanity check, push, open PR

**Files:**
- None (verification and remote operations only)

Even though no code was touched, a quick run of the existing checks confirms nothing accidentally broke (e.g. via line-ending changes a `.md` editor might have introduced into the wrong place). Then push and open the PR.

- [ ] **Step 1: Verify the test suite, lint, and types still pass**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: all four commands exit 0. `pytest` shows coverage ≥ 95% with all tests passing. If anything fails, stop and investigate — docs-only changes should not affect any of these.

- [ ] **Step 2: Review the full diff against `main`**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter log --oneline main..phase-1b-cycle-5
git -C /Users/tane/Code/mt5-pnl-exporter diff --stat main..phase-1b-cycle-5
```

Expected: commits from Tasks 1–5 plus the spec commit (`de99dcb`). Files changed: at minimum `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md`, plus `docs/superpowers/specs/2026-06-03-phase-1b-cycle-5-design.md` (from the spec commit) and this plan file. `CLAUDE.md` may or may not be in the list depending on Task 1's audit result.

- [ ] **Step 3: Push the branch**

```bash
git -C /Users/tane/Code/mt5-pnl-exporter push -u origin phase-1b-cycle-5
```

Expected: push succeeds; remote branch tracking set up.

- [ ] **Step 4: Open the PR**

```bash
gh pr create --repo tanem/mt5-pnl-exporter \
  --base main \
  --head phase-1b-cycle-5 \
  --title "Phase 1b cycle 5: pre-publish docs polish" \
  --body "$(cat <<'EOF'
## Summary

- Rewrites `README.md` to the art-of-readme structure: badges row, contract-first tagline, family-of-tools diagram, Contents TOC, Why bullets, Quick start showing both the terminal session and the decrypted snapshot shape, and a new How it works section with the gzip + age pipeline diagram. `## Status` dropped — the PyPI badge and the major.minor paragraph in `## Schema` carry stability messaging.
- Adds `SECURITY.md` (vuln-reporting policy, scoped to both investor passwords and the encryption passphrase) and `CONTRIBUTING.md` (setup, tests, schema-regen).
- Updates the cycle 4 spec's sequence diagram to anticipate cycle 6 (codecov) between cycle 5 and the 1.0 tag.
- No code changes.

## Test plan

- [ ] `uv run pytest` passes locally (coverage ≥ 95%)
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/mt5_pnl_exporter` clean
- [ ] CI workflow green on the PR
- [ ] `gh api /markdown` render check passed for each edited `.md` file
- [ ] Visual review of both ASCII diagrams on the rendered GitHub README

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR is created, ready for review (not draft). Print the returned URL.

- [ ] **Step 5: Confirm the PR is regular (not draft)**

```bash
gh pr view --repo tanem/mt5-pnl-exporter --json isDraft,url
```

Expected: `{"isDraft": false, "url": "..."}`. If `isDraft` is true, run `gh pr ready` to flip it.
