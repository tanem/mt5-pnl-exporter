# Renovate Dependency Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Renovate to auto-update GitHub Actions (SHA-pinned) and Python dependencies, with documentation of the update flow and supply-chain controls.

**Architecture:** A single `renovate.json` at the repo root drives everything via the `helpers:pinGitHubActionDigests` preset (pins actions to commit SHAs) and `config:recommended` (manages Actions + `pyproject.toml`/`uv.lock`). `packageRules` auto-merge digest/minor/patch on green CI and force majors and any `MetaTrader5` bump to open a PR. Docs land in CONTRIBUTING.md, SECURITY.md, and CLAUDE.md. No application code changes.

**Tech Stack:** Renovate (config JSON), `renovate-config-validator` (via `npx`), existing Python toolchain unchanged.

**Spec:** [`docs/superpowers/specs/2026-06-06-renovate-dependency-automation-design.md`](../specs/2026-06-06-renovate-dependency-automation-design.md)

**Note on TDD:** There is no application code in this change, so the usual write-failing-test cycle does not apply. The verification analogue is `renovate-config-validator` (the config must parse and validate) plus confirming the existing test suite stays green (no code touched). Each task ends with an explicit verification command and a commit.

---

## File Structure

- **Create:** `renovate.json` — the entire Renovate configuration (presets, lockfile maintenance, package rules).
- **Modify:** `CONTRIBUTING.md` — add a "Dependency updates" section describing the Renovate PR flow.
- **Modify:** `SECURITY.md` — add SHA-pinning + lockfile maintenance to the controls/scope.
- **Modify:** `CLAUDE.md` — add a gotcha so future agent sessions do not hand-bump or un-pin Renovate-managed dependencies.

---

### Task 1: Create and validate `renovate.json`

**Files:**
- Create: `renovate.json`

- [ ] **Step 1: Write the config**

Create `renovate.json` at the repo root with exactly this content:

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "helpers:pinGitHubActionDigests"
  ],
  "lockFileMaintenance": {
    "enabled": true
  },
  "packageRules": [
    {
      "description": "Auto-merge digest, minor and patch updates once CI passes",
      "matchUpdateTypes": ["digest", "minor", "patch"],
      "automerge": true
    },
    {
      "description": "Major updates always open a PR for review",
      "matchUpdateTypes": ["major"],
      "automerge": false
    },
    {
      "description": "MetaTrader5 is a Windows-only optional extra CI cannot validate; always review",
      "matchPackageNames": ["MetaTrader5"],
      "automerge": false
    }
  ]
}
```

The `MetaTrader5` rule is intentionally last: `packageRules` apply in order and later rules override earlier ones, so its `automerge: false` wins over the update-type rules for any `MetaTrader5` update.

- [ ] **Step 2: Validate the config (the "test")**

Run: `npx --yes renovate-config-validator renovate.json`

Expected: output ends with `INFO: Config validated successfully` and exit code 0. If it reports an unknown option or invalid preset, fix the config and re-run before proceeding.

- [ ] **Step 3: Confirm the existing suite is unaffected**

Run: `uv run pytest -q`

Expected: PASS — no app code changed, coverage gate still met.

- [ ] **Step 4: Commit**

```bash
git add renovate.json
git commit -m "ci: add Renovate config for actions + python deps

Pins GitHub Actions to commit SHAs via helpers:pinGitHubActionDigests
and manages pyproject/uv.lock via config:recommended. Auto-merges
digest/minor/patch on green CI; majors and MetaTrader5 open a PR.
lockFileMaintenance enabled for transitive patches.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Document the update flow in CONTRIBUTING.md

**Files:**
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Add a "Dependency updates" section**

Insert a new section immediately before the existing `## Conventions` section (currently the last section). The existing text to anchor on is:

```markdown
## Conventions

See [`CLAUDE.md`](CLAUDE.md) — the canonical reference for coding style, architectural rules, and gotchas (NZ English, no module-level `MetaTrader5` import, doc-sync rule, etc.). It's loaded automatically by Claude Code but reads as a normal project doc.
```

Replace it with:

```markdown
## Dependency updates

Dependencies are kept current by [Renovate](https://docs.renovatebot.com/) (config: [`renovate.json`](renovate.json)), which manages both GitHub Actions and Python dependencies (`pyproject.toml` / `uv.lock`):

- GitHub Actions are pinned to commit SHAs (not mutable tags) for supply-chain integrity; Renovate keeps the SHA and its version comment current.
- Digest, minor, and patch updates **auto-merge** once the `tests` workflow passes.
- Major updates, and any `MetaTrader5` bump (Windows-only optional extra that CI cannot exercise), open a PR for manual review.
- `lockFileMaintenance` periodically refreshes `uv.lock` to pick up transitive security patches.

Don't hand-bump these versions — let Renovate's PRs flow through.

## Conventions

See [`CLAUDE.md`](CLAUDE.md) — the canonical reference for coding style, architectural rules, and gotchas (NZ English, no module-level `MetaTrader5` import, doc-sync rule, etc.). It's loaded automatically by Claude Code but reads as a normal project doc.
```

- [ ] **Step 2: Verify the edit landed**

Run: `grep -n "Dependency updates" CONTRIBUTING.md`

Expected: one match for the new heading.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: document Renovate update flow in CONTRIBUTING

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Record supply-chain controls in SECURITY.md

**Files:**
- Modify: `SECURITY.md`

- [ ] **Step 1: Add a "Supply-chain controls" section**

Insert a new section immediately after the `## Scope` section and before `## Reporting`. The existing text to anchor on is the end of the Scope section followed by the Reporting heading:

```markdown
- Issues only reproducible with a non-current Python or uv version

## Reporting
```

Replace it with:

```markdown
- Issues only reproducible with a non-current Python or uv version

## Supply-chain controls

- **GitHub Actions are pinned to commit SHAs** (not mutable tags), so a compromised or retagged action cannot inject code into CI. [Renovate](https://docs.renovatebot.com/) keeps the pins current via `helpers:pinGitHubActionDigests`.
- **`lockFileMaintenance`** periodically refreshes `uv.lock` so transitive dependency security patches are picked up rather than pinned indefinitely.
- Dependency update PRs (Renovate) must pass the full `tests` workflow before merging; see [`renovate.json`](renovate.json) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Reporting
```

- [ ] **Step 2: Verify the edit landed**

Run: `grep -n "Supply-chain controls" SECURITY.md`

Expected: one match for the new heading.

- [ ] **Step 3: Commit**

```bash
git add SECURITY.md
git commit -m "docs: record SHA-pinning and lockfile maintenance in SECURITY

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Add a Renovate gotcha to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the gotcha bullet**

In the `## Gotchas` section, the final bullet is currently:

```markdown
- **`SCHEMA_VERSION` is `"1.0"`** (major.minor string). `read()` accepts the same major up to its own minor; bump the minor for additive fields, the major for breaking changes.
```

Add a new bullet immediately after it:

```markdown
- **Dependencies are Renovate-managed; don't hand-bump them.** GitHub Actions in `.github/workflows/` are pinned to commit SHAs (with a trailing version comment) and Python deps in `pyproject.toml`/`uv.lock` are tracked by `renovate.json`. Renovate opens the update PRs (digest/minor/patch auto-merge on green CI; majors and `MetaTrader5` open a PR). Do not replace a pinned SHA with a tag or manually bump a version — it fights the bot.
```

- [ ] **Step 2: Verify the edit landed**

Run: `grep -n "Renovate-managed" CLAUDE.md`

Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note Renovate-managed deps in CLAUDE gotchas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Re-validate the Renovate config**

Run: `npx --yes renovate-config-validator renovate.json`

Expected: `Config validated successfully`, exit code 0.

- [ ] **Step 2: Confirm the full CI-equivalent suite is green**

Run:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
uv run pytest -q
```

Expected: all PASS. (No source changed, so this is a sanity check that nothing was disturbed.)

- [ ] **Step 3: Confirm the working tree is clean and commits are present**

Run: `git log --oneline -6 && git status`

Expected: the five commits from Tasks 1–4 (plus the spec commit) present; working tree clean.

---

## Manual prerequisites (maintainer, outside this plan)

These cannot be done from the repo and gate auto-merge actually working. Surface them to the maintainer after implementation:

1. Install the **Renovate GitHub App** on `tanem/mt5-pnl-exporter`.
2. Enable **"Allow auto-merge"** in repository Settings → General.

After install, Renovate opens an onboarding PR plus the SHA-pinning PR for the four current actions.

---

## Self-Review

**Spec coverage:**
- Renovate config (presets, scope, lockfile, package rules) → Task 1. ✓
- SHA-pinning via preset → Task 1 (`helpers:pinGitHubActionDigests`). ✓
- Auto-merge digest/minor/patch, majors PR, MetaTrader5 PR → Task 1 package rules. ✓
- Docs in CONTRIBUTING / SECURITY / CLAUDE, not README → Tasks 2/3/4. ✓
- Manual prerequisites surfaced → dedicated section. ✓
- Verification (config validator + suite green) → Tasks 1 & 5. ✓
- Out-of-scope items (Dependabot, hand-pinning, README, CI improvements) → not present in any task. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/vague steps. All edits show exact old/new text. ✓

**Type/name consistency:** Preset names (`config:recommended`, `helpers:pinGitHubActionDigests`), `lockFileMaintenance`, `matchUpdateTypes`, `matchPackageNames`, and `MetaTrader5` are spelled identically across the config and all docs. ✓
