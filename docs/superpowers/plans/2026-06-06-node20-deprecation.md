# Node.js 20 GHA deprecation follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump four GitHub Actions in `.github/workflows/ci.yml` off Node 20 by moving each to its current latest major (`checkout@v6`, `setup-python@v6`, `setup-uv@v8`, `codecov-action@v6`) before GitHub's 2026-06-16 force-bump deadline.

**Architecture:** One file changes (`ci.yml`). Four single-line version-pin updates. Each bump is committed separately so `git bisect` can identify a culprit if the PR's CI run regresses. Easiest bump first, biggest jump last.

**Tech Stack:** GitHub Actions workflow YAML.

**Reference spec:** [`docs/superpowers/specs/2026-06-06-node20-deprecation-design.md`](../specs/2026-06-06-node20-deprecation-design.md)

---

## File map

| Path | Action | Purpose |
| --- | --- | --- |
| `.github/workflows/ci.yml` | modify | Bump four `uses:` pins, one commit per action. |

---

## Task 0: Branch state verification

**Files:** none (git only)

- [ ] **Step 0.1: Confirm branch and clean tree**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git status
git log --oneline -3
```

Expected: on branch `chore-node20-deprecation`, working tree clean, HEAD at `17c456f` (the spec commit). The branch was already cut and the spec already committed during brainstorming.

If the branch isn't there or the tree isn't clean, stop and investigate before proceeding.

- [ ] **Step 0.2: Confirm current ci.yml state**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
grep -nE "uses: (actions/checkout|actions/setup-python|astral-sh/setup-uv|codecov/codecov-action)" .github/workflows/ci.yml
```

Expected (exact output):

```
13:      - uses: actions/checkout@v4
14:      - uses: actions/setup-python@v5
17:      - uses: astral-sh/setup-uv@v4
24:      - uses: codecov/codecov-action@v5
```

Four pins, all at the pre-bump versions. If any differ, stop — the file state has drifted from the spec and the line numbers below won't apply cleanly.

---

## Task 1: Bump `actions/checkout` v4 → v6

**Files:**
- Modify: `.github/workflows/ci.yml:13`

Smallest blast radius first. Our usage is the bare `- uses: actions/checkout@v4` with no `with:` inputs.

- [ ] **Step 1.1: Edit the pin**

Find this line in `.github/workflows/ci.yml`:

```yaml
      - uses: actions/checkout@v4
```

Change to:

```yaml
      - uses: actions/checkout@v6
```

Only the `v4` → `v6` token changes. The 6-space indent and the leading `- uses:` stay identical.

- [ ] **Step 1.2: Validate the workflow still parses**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 1.3: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add .github/workflows/ci.yml
git commit -m "ci: bump actions/checkout to v6 (Node 24)"
```

Pre-commit (gitleaks + ruff) should pass cleanly.

---

## Task 2: Bump `actions/setup-python` v5 → v6

**Files:**
- Modify: `.github/workflows/ci.yml:14`

Our usage uses one input (`python-version: "3.12"`) — the canonical name, stable across v3–v6.

- [ ] **Step 2.1: Edit the pin**

Find this line:

```yaml
      - uses: actions/setup-python@v5
```

Change to:

```yaml
      - uses: actions/setup-python@v6
```

The following `with:` block (lines 15-16, `python-version: "3.12"`) stays untouched — `python-version` is unchanged in v6.

- [ ] **Step 2.2: Validate the workflow still parses**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 2.3: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add .github/workflows/ci.yml
git commit -m "ci: bump actions/setup-python to v6 (Node 24)"
```

---

## Task 3: Bump `codecov/codecov-action` v5 → v6

**Files:**
- Modify: `.github/workflows/ci.yml:24`

v6's only purpose is bumping the transitive `actions/github-script` dependency to v8 (Node 24). Inputs `token`, `slug`, `files` are verified unchanged in v6's `action.yml`.

- [ ] **Step 3.1: Edit the pin**

Find this line:

```yaml
      - uses: codecov/codecov-action@v5
```

Change to:

```yaml
      - uses: codecov/codecov-action@v6
```

The following `with:` block (token / slug / files) stays untouched.

- [ ] **Step 3.2: Validate the workflow still parses**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 3.3: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add .github/workflows/ci.yml
git commit -m "ci: bump codecov/codecov-action to v6 (Node 24 via github-script v8)"
```

---

## Task 4: Bump `astral-sh/setup-uv` v4 → v8

**Files:**
- Modify: `.github/workflows/ci.yml:17`

Biggest jump (four majors). Our usage is the bare `- uses: astral-sh/setup-uv@v4` with no `with:` inputs — we want `uv` on `PATH`, nothing else. The v8 default behaviour matches.

If this commit's CI run regresses, the fallback decision (pin to `@v7` instead) lives at the end of this task — only invoke it after the PR's run actually fails.

- [ ] **Step 4.1: Edit the pin**

Find this line:

```yaml
      - uses: astral-sh/setup-uv@v4
```

Change to:

```yaml
      - uses: astral-sh/setup-uv@v8
```

- [ ] **Step 4.2: Validate the workflow still parses**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 4.3: Confirm the full diff so far**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git diff main..HEAD -- .github/workflows/ci.yml
```

Expected: four lines changed (the four `uses:` pins above), nothing else. The `python-version`, `token`, `slug`, `files` lines and all `- run:` steps must be untouched.

- [ ] **Step 4.4: Commit**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git add .github/workflows/ci.yml
git commit -m "ci: bump astral-sh/setup-uv to v8 (Node 24)"
```

- [ ] **Step 4.5: Fallback note (only if the PR's CI run later fails on this step)**

This step is a placeholder — do NOT execute it unless the PR's CI run fails specifically on the `setup-uv` step. If it does:

```yaml
      - uses: astral-sh/setup-uv@v7
```

Commit as: `ci: pin astral-sh/setup-uv to v7 (v8 regressed)`. Push, re-run CI. Then revisit whether to investigate the v8 regression or stay at v7.

---

## Task 5: Local sanity check before push

**Files:** none (verification only)

Local YAML parsing already passed in each task. This step is the cumulative diff review and a final eyeball.

- [ ] **Step 5.1: Show the full cumulative diff vs `main`**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git diff main..HEAD -- .github/workflows/ci.yml
```

Expected: exactly four `-` / `+` line pairs, each changing only the version token after `@`. The four lines must change to:

```
- uses: actions/checkout@v6
- uses: actions/setup-python@v6
- uses: astral-sh/setup-uv@v8
- uses: codecov/codecov-action@v6
```

If any other line shows up in the diff, stop and reconcile before pushing.

- [ ] **Step 5.2: Confirm commit log**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git log --oneline main..HEAD
```

Expected output (newest first, since that's `git log`'s default):

```
<sha> ci: bump astral-sh/setup-uv to v8 (Node 24)
<sha> ci: bump codecov/codecov-action to v6 (Node 24 via github-script v8)
<sha> ci: bump actions/setup-python to v6 (Node 24)
<sha> ci: bump actions/checkout to v6 (Node 24)
<sha> docs: Node.js 20 GHA deprecation follow-up design
```

Five commits total — one spec + four bumps, in the task order from this plan.

- [ ] **Step 5.3: Confirm pytest still passes locally**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
uv run pytest 2>&1 | tail -3
```

Expected: `84 passed`, coverage 100%. The GHA bumps don't touch any Python — pytest passing is just a sanity check that nothing collateral leaked into the working tree.

---

## Task 6: Push branch and open PR

**Files:** none (git + gh)

- [ ] **Step 6.1: Push**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git push -u origin chore-node20-deprecation
```

Expected: branch pushed, CI run kicks off automatically.

- [ ] **Step 6.2: Open the PR (regular, not draft)**

```bash
gh pr create --repo tanem/mt5-pnl-exporter \
  --title "ci: bump GHA actions off Node 20 (deadline 2026-06-16)" \
  --body "$(cat <<'EOF'
## Summary

Bumps four GitHub Actions in `.github/workflows/ci.yml` to their current latest majors so the workflow runs on Node 24 directly instead of GitHub's force-bump default that kicks in on 2026-06-16:

- `actions/checkout@v4` → `@v6`
- `actions/setup-python@v5` → `@v6`
- `astral-sh/setup-uv@v4` → `@v8`
- `codecov/codecov-action@v5` → `@v6` (the v6 release's sole purpose is bumping the transitive `actions/github-script` dep to v8 / Node 24)

Spec: [`docs/superpowers/specs/2026-06-06-node20-deprecation-design.md`](docs/superpowers/specs/2026-06-06-node20-deprecation-design.md)
Plan: [`docs/superpowers/plans/2026-06-06-node20-deprecation.md`](docs/superpowers/plans/2026-06-06-node20-deprecation.md)

Slips in between cycle-6's merge and the manual 1.0.0 tag — the deadline is too close to wait for a publish first, and a clean CI surface matters for the tagged commit.

## Test plan

- [ ] PR CI run green (no Node 20 deprecation warning in the job summary)
- [ ] `codecov/codecov-action@v6` upload step succeeds; Codecov PR comment appears
- [ ] No regressions in the `test` workflow vs the cycle-6 main-branch run
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 6.3: Watch the first CI run**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
gh pr checks --watch
```

Expected: `test`, `codecov/patch`, `codecov/project` all green. The job summary in the GitHub UI should no longer show the Node 20 deprecation banner.

If anything fails, identify which step (most likely candidates: `setup-uv@v8` install behaviour, `codecov-action@v6` upload). Then either:
- (setup-uv only) follow Task 4 step 4.5 to pin back to `@v7`.
- (codecov-action) inspect the failing step's log against the v6 action.yml inputs we verified during brainstorming; the three inputs we set (`token`, `slug`, `files`) are unchanged, so any breakage would be a runtime issue worth filing upstream.
