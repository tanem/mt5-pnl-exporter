# MT5 Host-Setup Onboarding Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the README walk a first-timer through preparing the MT5 host before their first export, fix the stale/contradictory `terminal_path` examples, and give maintainers a from-clone real-export smoke test in CONTRIBUTING.

**Architecture:** Docs-only change across three files — `README.md` (new "Prepare the MT5 host" section + Install/Quick-start/Configuration touch-ups), `config.example.yaml` (one-line fix), and `CONTRIBUTING.md` (new "Smoke-test a real export" section). No code, schema, or tests are touched. The single dedicated-terminal path `C:\Program Files\MT5 Exporter\terminal64.exe` must be consistent everywhere it appears.

**Tech Stack:** Markdown, YAML. Verification via `grep` and reading rendered anchors. No build step.

**Spec:** [`docs/superpowers/specs/2026-06-08-host-setup-onboarding-docs-design.md`](../specs/2026-06-08-host-setup-onboarding-docs-design.md)

**Conventions reminder:** NZ English (realise, behaviour, colour). No hyperbole. The work is on branch `docs/host-setup-onboarding` (already created, with the spec committed).

---

### Task 1: Add the "Prepare the MT5 host" section to README

**Files:**
- Modify: `README.md` (Contents list ~line 28; new section inserted between the Install section and the Quick start heading)

- [ ] **Step 1: Add the Contents-list entry**

Use Edit on `README.md`. Find:

```markdown
- [Why](#why)
- [Install](#install)
- [Quick start](#quick-start)
```

Replace with:

```markdown
- [Why](#why)
- [Install](#install)
- [Prepare the MT5 host](#prepare-the-mt5-host)
- [Quick start](#quick-start)
```

- [ ] **Step 2: Insert the new section before Quick start**

The Install section currently ends with this fenced block, immediately followed by the Quick start heading:

```markdown
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Quick start
```

Use Edit to find that `## Quick start` heading line (the one right after the Install code fence) and insert the new section ahead of it. Find:

```markdown
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Quick start
```

Replace with:

```markdown
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Prepare the MT5 host

Do this once on the Windows host, before your first export.

### A dedicated MT5 terminal

The exporter needs its **own** MT5 terminal — *not* a terminal running your EAs. `mt5.login()` switches the connected terminal's active account, so pointing the exporter at an EA terminal would log your EA out and halt trading. A dedicated, idle terminal (no EA attached) runs alongside your EA terminals without touching them. The investor login and your EA's master login are independent, concurrent sessions.

Install a second MT5 to its own path — e.g. `C:\Program Files\MT5 Exporter\` — separate from any EA terminal.

### First-run login

Launch the dedicated terminal once, manually, log in with any of your investor passwords, dismiss any first-run dialogs, then close it. This saves the server config and clears the open-account wizard. **Skip this and `export` fails with `(-10005, 'IPC timeout')`** — the wizard on a fresh install blocks the API.

### Finding your config values

- `terminal_path` — full path to the dedicated terminal's `terminal64.exe` (e.g. `C:\Program Files\MT5 Exporter\terminal64.exe`).
- `login` — the account number (the MT5 login).
- `server` — the broker server name, shown in MT5's login dialog (e.g. `BrokerName-Live`).

## Quick start
```

- [ ] **Step 3: Verify the section and anchor**

Run: `grep -n "## Prepare the MT5 host" README.md` and `grep -n "prepare-the-mt5-host" README.md`
Expected: the heading appears once; the Contents anchor appears once. Confirm the heading sits after the Install code fence and before `## Quick start`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add Prepare the MT5 host section to README"
```

---

### Task 2: Add Install uv one-liner and Quick-start lead-in

**Files:**
- Modify: `README.md` (Install section ~line 48; Quick start heading ~line 53)

- [ ] **Step 1: Add the Windows uv bootstrap above the install commands**

Use Edit on `README.md`. Find:

```markdown
## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
```

Replace with:

```markdown
## Install

On a bare Windows host, install `uv` first:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the exporter:

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
```

- [ ] **Step 2: Add the Quick-start prerequisite lead-in**

The Quick start heading is immediately followed by a fenced `bash` block starting with `$ mt5-pnl-exporter set-investor-password 1234567`. Use Edit to find:

```markdown
## Quick start

```bash
$ mt5-pnl-exporter set-investor-password 1234567
```

Replace with:

```markdown
## Quick start

Once the [MT5 host is prepared](#prepare-the-mt5-host):

```bash
$ mt5-pnl-exporter set-investor-password 1234567
```

- [ ] **Step 3: Verify**

Run: `grep -n "astral.sh/uv/install.ps1" README.md` and `grep -n "MT5 host is prepared" README.md`
Expected: each appears exactly once.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add Windows uv bootstrap and quick-start prerequisite"
```

---

### Task 3: Fix the stale terminal_path in README and config.example.yaml

**Files:**
- Modify: `README.md` (Configuration block ~line 124)
- Modify: `config.example.yaml` (line 2)

- [ ] **Step 1: Fix the README Configuration block**

Use Edit on `README.md`. Find:

```yaml
terminal_path: C:\mt5-poller\terminal64.exe
```

Replace with:

```yaml
terminal_path: C:\Program Files\MT5 Exporter\terminal64.exe
```

- [ ] **Step 2: Fix config.example.yaml**

Use Edit on `config.example.yaml`. Find:

```yaml
terminal_path: C:\Program Files\MetaTrader 5\terminal64.exe
```

Replace with:

```yaml
terminal_path: C:\Program Files\MT5 Exporter\terminal64.exe
```

- [ ] **Step 3: Verify both stale values are gone and the new one is consistent**

Run:
```bash
grep -rn "mt5-poller" README.md config.example.yaml
grep -rn "MetaTrader 5..terminal64" README.md config.example.yaml
grep -rn "MT5 Exporter..terminal64.exe" README.md config.example.yaml
```
Expected: the first two greps print nothing (exit 1); the third prints two lines (one per file), both `C:\Program Files\MT5 Exporter\terminal64.exe`.

- [ ] **Step 4: Commit**

```bash
git add README.md config.example.yaml
git commit -m "docs: point terminal_path at a dedicated MT5 Exporter terminal"
```

---

### Task 4: Add the "Smoke-test a real export" section to CONTRIBUTING

**Files:**
- Modify: `CONTRIBUTING.md` (insert between the "Regenerating the schema" section and the "Dependency updates" heading, ~line 31)

- [ ] **Step 1: Insert the new section**

Use Edit on `CONTRIBUTING.md`. Find:

```markdown
`tests/test_schema_file.py` fails CI if the committed schema drifts from the model. Commit the regenerated file alongside the model change.

## Dependency updates
```

Replace with:

```markdown
`tests/test_schema_file.py` fails CI if the committed schema drifts from the model. Commit the regenerated file alongside the model change.

## Smoke-test a real export

Before publishing a new version, exercise a real MT5 export from your working tree. `MetaTrader5` is Windows-only, so this runs on the Windows host where MT5 lives — the cross-platform checks (`pytest`, `ruff`, `mypy`) run anywhere.

1. Prepare the host once — see the README's [Prepare the MT5 host](README.md#prepare-the-mt5-host) section (dedicated terminal + first-run login).
2. `uv sync --extra mt5` — install dependencies including `MetaTrader5` from the clone.
3. Store credentials if you haven't already: `uv run mt5-pnl-exporter set-investor-password <login>` and `uv run mt5-pnl-exporter set-encryption-passphrase`.
4. `cp config.example.yaml config.yaml` and fill in `terminal_path` and `accounts`.
5. `uv run mt5-pnl-exporter export` — confirm it logs `OK` per account and writes the snapshot.

Steps 2–5 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point, the `[mt5]` extra, the bundled schema file), build and install the wheel before publishing:

```bash
uv build                                   # produces dist/*.whl
uv tool install "./dist/mt5_pnl_exporter-<ver>-py3-none-any.whl[mt5]"
mt5-pnl-exporter export                    # runs the installed tool, not the clone
```

## Dependency updates
```

- [ ] **Step 2: Verify the section and cross-link**

Run: `grep -n "## Smoke-test a real export" CONTRIBUTING.md` and `grep -n "README.md#prepare-the-mt5-host" CONTRIBUTING.md`
Expected: each appears exactly once. The cross-link target must match the README anchor created in Task 1.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add maintainer real-export smoke test to CONTRIBUTING"
```

---

### Task 5: Final consistency sweep and CLAUDE.md doc-sync check

**Files:**
- Read-only: `README.md`, `config.example.yaml`, `CONTRIBUTING.md`, `CLAUDE.md`

- [ ] **Step 1: Confirm no stale terminal paths remain anywhere**

Run:
```bash
grep -rn "mt5-poller" .
grep -rn "MetaTrader 5..terminal64" .
```
Expected: nothing under tracked docs/config (the spec file may legitimately mention these as the values being removed — that is fine and expected; confirm no *other* file still presents them as the live example).

- [ ] **Step 2: Confirm the dedicated path is the single example everywhere**

Run: `grep -rn "MT5 Exporter" README.md config.example.yaml CONTRIBUTING.md`
Expected: README (section prose + Finding-your-config-values + Configuration block) and config.example.yaml all show `C:\Program Files\MT5 Exporter\`. No conflicting variants.

- [ ] **Step 3: Verify the CLAUDE.md gotcha does not contradict the new wording**

Read the dedicated-terminal gotcha in `CLAUDE.md` ("A dedicated MT5 terminal is required: `mt5.login()` switches the terminal's active account, so pointing it at an EA terminal logs the EA out."). Confirm it agrees with the README's new "A dedicated MT5 terminal" subsection. Per the spec, no CLAUDE.md edit is expected — only make a change if an actual contradiction is found; if so, align CLAUDE.md and note it in the commit.

- [ ] **Step 4: Verify no code or tests were touched**

Run: `git diff --name-only main...HEAD`
Expected: only `README.md`, `config.example.yaml`, `CONTRIBUTING.md`, and the two `docs/superpowers/` files (spec + plan). No files under `src/` or `tests/`.

- [ ] **Step 5: Open the PR**

```bash
git push -u origin docs/host-setup-onboarding
gh pr create --title "docs: MT5 host-setup onboarding" --body "$(cat <<'EOF'
Adds a README "Prepare the MT5 host" section (dedicated terminal rationale, first-run login ritual, the -10005 IPC timeout failure mode, and where to find terminal_path/login/server), a Windows uv bootstrap one-liner, and a quick-start prerequisite lead-in. Fixes two stale/contradictory terminal_path examples (README's C:\mt5-poller and config.example.yaml's default MetaTrader 5 path) to a single dedicated C:\Program Files\MT5 Exporter\terminal64.exe. Adds a CONTRIBUTING "Smoke-test a real export" section for maintainers.

Docs-only — no code, schema, or tests changed.

Spec: docs/superpowers/specs/2026-06-08-host-setup-onboarding-docs-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes for the executor

- This is a **docs-only** change. There is no test suite to run for these edits; verification is the `grep`/read checks in each task. Do **not** add or modify code to satisfy a step.
- Preserve exact backslash paths (`C:\Program Files\MT5 Exporter\terminal64.exe`) — these are Windows paths in Markdown/YAML, not escapes.
- NZ English throughout (the prose already uses "realise/behaviour"; match it).
- The branch `docs/host-setup-onboarding` already exists and carries the committed spec; commit each task onto it.
