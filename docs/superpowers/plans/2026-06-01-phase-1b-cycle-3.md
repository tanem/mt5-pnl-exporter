# Phase 1b Cycle 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the docs reframe, threat model, and keychain audit that close out the security framing for the 1.0 release. Three docs deliverables (README threat model section, Windows-host reframe across README and CLAUDE.md, new `docs/security-audit.md`) plus two small audit-driven `secrets.py` patches (empty-string guards on both setters, `redact_filter.scrub` helper).

**Architecture:** The code patches are contained inside `src/mt5_pnl_exporter/secrets.py` and exercised through `tests/test_secrets.py`; no other module changes. The audit doc cites the patch commit SHA so a reader can browse from finding to fix. The threat-model section lives in `README.md` (one well-bounded section between `## Snapshot size` and `## Status`); the Windows-host reframe is a small set of in-place wording edits across `README.md` and `CLAUDE.md` with no structural change. Three implementation tasks land in order — code first, docs second, audit third — so the audit can quote the code commit's SHA. A fourth task verifies the branch and opens the draft PR.

**Tech Stack:** Python 3.12, pydantic 2, Typer, pytest with coverage, ruff, mypy, uv. GitHub CLI (`gh`) for the PR step and the markdown render check. Working directory throughout this plan: `/Users/tane/Code/mt5-pnl-exporter`.

**Reference spec:** [`docs/superpowers/specs/2026-06-01-phase-1b-cycle-3-design.md`](../specs/2026-06-01-phase-1b-cycle-3-design.md).

**Branch:** `phase-1b-cycle-3` from `main` (currently `7de2e28`). No direct pushes to `main`.

---

## File Structure (final state)

```
src/mt5_pnl_exporter/
└── secrets.py          # +empty-string guard on set_investor_password
                        # +empty-string guard on set_encryption_passphrase
                        # +redact_filter.scrub(s) helper

tests/
└── test_secrets.py     # +3 tests: empty-string rejection on both setters
                        # +3 tests: scrub helper behaviours

docs/
├── security-audit.md   # NEW: dated audit doc with table + findings
└── superpowers/
    ├── specs/2026-06-01-phase-1b-cycle-3-design.md   # already on main
    └── plans/2026-06-01-phase-1b-cycle-3.md          # this file

README.md               # +## Threat model section; VPS → Windows-host wording
CLAUDE.md               # VPS → Windows-host wording in intro, commands, gotcha
```

No new top-level files, no new dependencies, no schema changes.

---

## Task 1: `secrets.py` empty-string guards and `redact_filter.scrub`

**Files:**
- Modify: `src/mt5_pnl_exporter/secrets.py`
- Modify: `tests/test_secrets.py`

- [ ] **Step 1: Create and check out the working branch**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git fetch origin
git checkout -b phase-1b-cycle-3 origin/main
git log --oneline -1
```

Expected: HEAD is `7de2e28 docs: fix audit-table preview rendering in cycle 3 spec` (or whatever the current tip of `main` is). The branch starts clean.

- [ ] **Step 2: Add the failing test for empty-string `set_investor_password`**

Add `import pytest` to the imports block at the top of `tests/test_secrets.py` (it does not import pytest today). Then append this test at the end of the file:

```python
def test_set_investor_password_rejects_empty():
    """Empty password is rejected at the library boundary, before keyring is touched."""
    with patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set:
        with pytest.raises(ValueError, match="password cannot be empty"):
            set_investor_password(12345, "")
    mock_set.assert_not_called()
```

- [ ] **Step 3: Run the new test and confirm it fails**

Run: `uv run pytest tests/test_secrets.py::test_set_investor_password_rejects_empty -v`
Expected: FAIL. The failure is "DID NOT RAISE <class 'ValueError'>" — the current implementation calls `keyring.set_password` unconditionally.

- [ ] **Step 4: Add the empty-string guard to `set_investor_password`**

In `src/mt5_pnl_exporter/secrets.py`, replace the current `set_investor_password`:

```python
def set_investor_password(login: int, password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, str(login), password)
```

with:

```python
def set_investor_password(login: int, password: str) -> None:
    if not password:
        raise ValueError("password cannot be empty")
    keyring.set_password(KEYRING_SERVICE, str(login), password)
```

- [ ] **Step 5: Re-run the test**

Run: `uv run pytest tests/test_secrets.py::test_set_investor_password_rejects_empty -v`
Expected: PASS.

- [ ] **Step 6: Add the failing test for empty-string `set_encryption_passphrase`**

Append to `tests/test_secrets.py`:

```python
def test_set_encryption_passphrase_rejects_empty():
    """Empty passphrase is rejected at the library boundary, before keyring is touched."""
    with patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set:
        with pytest.raises(ValueError, match="passphrase cannot be empty"):
            set_encryption_passphrase("")
    mock_set.assert_not_called()
```

- [ ] **Step 7: Run the new test and confirm it fails**

Run: `uv run pytest tests/test_secrets.py::test_set_encryption_passphrase_rejects_empty -v`
Expected: FAIL with "DID NOT RAISE".

- [ ] **Step 8: Add the empty-string guard to `set_encryption_passphrase`**

In `src/mt5_pnl_exporter/secrets.py`, replace the current `set_encryption_passphrase`:

```python
def set_encryption_passphrase(passphrase: str) -> None:
    keyring.set_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT, passphrase)
```

with:

```python
def set_encryption_passphrase(passphrase: str) -> None:
    if not passphrase:
        raise ValueError("passphrase cannot be empty")
    keyring.set_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT, passphrase)
```

- [ ] **Step 9: Re-run the test**

Run: `uv run pytest tests/test_secrets.py::test_set_encryption_passphrase_rejects_empty -v`
Expected: PASS.

- [ ] **Step 10: Add the three failing tests for `redact_filter.scrub`**

Append to `tests/test_secrets.py`:

```python
def test_scrub_returns_input_unchanged_with_no_secrets():
    """No registered secrets → scrub is a no-op."""
    filt = _RedactFilter()
    assert filt.scrub("hello world") == "hello world"


def test_scrub_replaces_single_registered_secret():
    filt = _RedactFilter()
    filt.register("pw123")
    assert filt.scrub("hello pw123 world") == "hello *** world"


def test_scrub_handles_multiple_registered_secrets():
    filt = _RedactFilter()
    filt.register("pw123")
    filt.register("alpha")
    assert filt.scrub("alpha and pw123") == "*** and ***"
```

- [ ] **Step 11: Run the new tests and confirm they fail**

Run: `uv run pytest tests/test_secrets.py -k scrub -v`
Expected: 3 FAILures, each with `AttributeError: '_RedactFilter' object has no attribute 'scrub'`.

- [ ] **Step 12: Add the `scrub` method to `_RedactFilter`**

In `src/mt5_pnl_exporter/secrets.py`, inside the `_RedactFilter` class, add `scrub` as a new method below the existing `filter` method:

```python
    def scrub(self, s: str) -> str:
        """Return `s` with each registered secret replaced by ***.

        Companion to `filter` for sites that bypass the `logging`
        machinery (e.g. `rich.Console`). Existing call sites do not
        interpolate registered secrets; this helper is for any future
        site that might.
        """
        if not self._secrets:
            return s
        pattern = "|".join(self._secrets)
        return re.sub(pattern, "***", s)
```

(`re` is already imported at the top of the module.)

- [ ] **Step 13: Re-run the scrub tests**

Run: `uv run pytest tests/test_secrets.py -k scrub -v`
Expected: 3 PASSes.

- [ ] **Step 14: Run the full suite, lint, format check, and type check**

Run all four in sequence:

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: full suite passes (coverage ≥ 95% — `test_secrets.py` now has six new tests, all exercising covered branches); ruff check clean; ruff format check clean; mypy clean.

If `ruff format --check` complains, run `uv run ruff format src/ tests/` and re-check.

- [ ] **Step 15: Commit**

```bash
git add src/mt5_pnl_exporter/secrets.py tests/test_secrets.py
git commit -m "feat(secrets): empty-string guards + redact_filter.scrub helper

Two audit findings from cycle 3:

- set_investor_password and set_encryption_passphrase now raise
  ValueError on empty input. The CLI guarded against this; the library
  did not. Defence in depth against programmatic misuse.
- redact_filter.scrub(s) returns the string with registered secrets
  replaced by ***. Covers rich.Console output, which bypasses the
  logging filter. No current err.print site interpolates a registered
  secret; the helper is available for any future site that needs it."
```

Expected: pre-commit secret-scan passes; commit lands on `phase-1b-cycle-3`.

Capture the new commit SHA — Task 3 cites it in `docs/security-audit.md`:

```bash
git rev-parse --short HEAD
```

Expected: short SHA printed (e.g. `abc1234`). Record this as `<TASK1_SHA>` for use in Task 3.

---

## Task 2: README threat model + Windows-host reframe (README + CLAUDE.md)

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

The framing edits and the new section land in one commit because the threat-model section reads off the reframed wording in the surrounding README sections; keeping them together avoids two PRs-worth of churn in the README.

- [ ] **Step 1: Reframe the README intro paragraph**

In `README.md`, the first paragraph currently reads:

> Polls MT5 deal history on a Windows VPS and writes `snapshot.json` — the
> published contract that downstream tools (CLI, UI) consume.

Edit to:

> Polls MT5 deal history on the Windows host where MT5 runs and writes
> `snapshot.json` — the published contract that downstream tools (CLI, UI)
> consume.

- [ ] **Step 2: Reframe the `## Install` block comment**

In the `## Install` block, the first code block currently reads:

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # VPS, includes MetaTrader5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

Edit to:

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

- [ ] **Step 3: Drop the `(VPS)` qualifier from the `## Quick start` heading**

The current heading reads:

```markdown
## Quick start (VPS)
```

Edit to:

```markdown
## Quick start
```

The commands inside the block do not change.

- [ ] **Step 4: Add the `## Threat model` section between `## Snapshot size` and `## Status`**

Insert this new section. Place it after the `## Snapshot size` block and before `## Status`.

```markdown
## Threat model

The OS user account on the Windows host that runs the exporter is the
trust boundary. Anyone with that account's session can read the
keychain, run `poll`, and read decrypted snapshots. The same applies
to a consumer machine: anyone with that account's session can decrypt
the snapshot. The exporter does not defend against a compromised user
session on either side.

### What's protected

- **Snapshot contents at rest off the Windows host.** Sync services
  (Dropbox, OneDrive, Syncthing), backups, and transit only ever see
  the gzipped, age-encrypted file. Mandatory encryption is what gets
  you this.
- **Investor passwords and the encryption passphrase, on disk and in
  logs.** Stored only in the OS keychain. The `redact_filter` strips
  any registered secret from log lines.

### What's not protected

- **A compromised user session on either host.** With keychain access
  the snapshot decrypts to plaintext.
- **Traffic-analysis metadata.** File size, sync timing, and whether a
  poll ran today are visible to anyone observing the transport. age
  hides contents, not existence.
- **Passphrase loss.** There is no recovery. The snapshot is
  reproducible, though — re-run `poll` to rebuild it from the broker's
  history.
- **The broker side.** MT5 deal history lives on the broker's server
  and is governed by their controls, not by anything in this tool.

### Transport guidance

Once the file is encrypted at rest, transport choice carries less
weight than it used to. scp/rsync over SSH, a synced folder
(Dropbox/Syncthing/OneDrive), or reading on the same machine are all
viable. Pick whichever fits the workflow.
```

- [ ] **Step 5: Reframe the CLAUDE.md intro paragraph**

In `CLAUDE.md`, the first paragraph currently begins:

> MT5 P&L exporter: a `uv`-managed Python 3.12 CLI (`mt5-pnl-exporter`) that polls
> MT5 deal history on a Windows VPS and writes `snapshot.json`. ...

Edit only the substring "on a Windows VPS" to "on the Windows host where MT5 runs". Final:

> MT5 P&L exporter: a `uv`-managed Python 3.12 CLI (`mt5-pnl-exporter`) that polls
> MT5 deal history on the Windows host where MT5 runs and writes `snapshot.json`. ...

Leave the rest of that paragraph unchanged.

- [ ] **Step 6: Reframe the CLAUDE.md commands block comment**

In the `## Commands` code block, the line currently reads:

```bash
uv sync --extra mt5                    # VPS: also install MetaTrader5
```

Edit to:

```bash
uv sync --extra mt5                    # Windows host: also install MetaTrader5
```

- [ ] **Step 7: Reframe the investor-password gotcha**

In the `## Gotchas` list, the bullet currently reads:

> **Investor passwords only**, stored in the VPS keychain via `keyring`. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `poll` only.

Edit to:

> **Investor passwords only**, stored in the OS keychain via `keyring` on the Windows host. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `poll` only.

Leave all other gotcha bullets unchanged.

- [ ] **Step 8: Run the markdown render check**

The standing preference is to render any non-trivial markdown edit via GitHub's renderer before committing. Run:

```bash
cat README.md | jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' \
  | gh api /markdown --input - > /tmp/cycle3-readme-rendered.html
grep -E -o '<h[1-6][^>]*>[^<]*' /tmp/cycle3-readme-rendered.html
```

Expected: the printed headings include `Threat model`, `What's protected`, `What's not protected`, and `Transport guidance` in order. Visual-only issues (spacing, list rendering) are flagged for human review rather than fixed automatically.

Repeat for CLAUDE.md if any structural concern remains; for the small in-place edits this plan makes, a render check is not required.

- [ ] **Step 9: Run lint on docs (markdown is not linted by ruff, but verify the test suite still passes)**

The docs changes do not touch code, but coverage gates run against committed files, so re-run the suite to confirm nothing regresses:

```bash
uv run pytest
```

Expected: green, coverage ≥ 95%.

- [ ] **Step 10: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: threat model section + Windows-host reframe

- README gains a ## Threat model section between ## Snapshot size and
  ## Status, structured as: trust boundary, what's protected, what's
  not protected, transport guidance.
- README and CLAUDE.md drop 'Windows VPS' framing in favour of 'the
  Windows host where MT5 runs'. VPS becomes one deployment choice
  among several, not the assumption.

Closes items 7 of phase 1b parent spec (docs reframe) and lands the
threat model that cycle 2 deferred."
```

Expected: commit lands on `phase-1b-cycle-3`.

---

## Task 3: `docs/security-audit.md`

**Files:**
- Create: `docs/security-audit.md`

- [ ] **Step 1: Substitute the Task 1 commit SHA**

This task's content cites the Task 1 commit. Retrieve the short SHA:

```bash
git log --oneline phase-1b-cycle-3 -- src/mt5_pnl_exporter/secrets.py | head -1
```

Expected: a single line whose first token is the short SHA (e.g. `abc1234 feat(secrets): empty-string guards + redact_filter.scrub helper`). Use that SHA wherever `<TASK1_SHA>` appears in Step 2.

- [ ] **Step 2: Create `docs/security-audit.md`**

Create the file with this content, replacing every `<TASK1_SHA>` with the SHA from Step 1:

````markdown
# Security audit — keychain reads, writes, and redaction boundaries

**Date:** 2026-06-01
**Branch:** `phase-1b-cycle-3`
**Audited commit:** `<TASK1_SHA>`

Audit of every keychain read/write and every site where a
keychain-sourced secret crosses a trust boundary in
`mt5-pnl-exporter`. Each row checks three properties: the secret is
never written to disk outside the keychain, never appears in log
output, and never crosses the `redact_filter` boundary unredacted.
Findings are listed below the table with patch references.

## Sites

| Site | Secret | Direction | Never on disk | Never in logs | Past redact boundary |
| --- | --- | --- | --- | --- | --- |
| `secrets.py::get_investor_password` | investor pw | keychain read | n/a | n/a | ✓ returns to caller |
| `secrets.py::set_investor_password` | investor pw | keychain write | ✓ | ✓ | ✓ accepts from caller |
| `secrets.py::get_encryption_passphrase` | passphrase | keychain read | n/a | n/a | ✓ returns to caller |
| `secrets.py::set_encryption_passphrase` | passphrase | keychain write | ✓ | ✓ | ✓ accepts from caller |
| `config.py::resolve_passwords` | investor pw | keychain read → dict | ✓ | ✓ (registered with `redact_filter` on read) | ✓ scoped to `MT5Source._passwords` |
| `cli.py::poll` (encryption passphrase load) | passphrase | keychain read → `snapshot.read/write` | ✓ | ✓ (registered with `redact_filter` on read) | ✓ goes only to `pyrage.passphrase.encrypt/decrypt` |
| `secrets.py::redact_filter` | n/a (boundary) | log filter | n/a | n/a | covers `logging` handlers only; `rich.Console` output bypasses it — see **Finding 2** |
| `config.py::check_file_perms` | n/a (boundary) | warn on `config.yaml` group/other-read | n/a | n/a | POSIX-only; no-op on Windows |

## Findings

### Finding 1 — `secrets.py` accepted empty secrets from callers

`set_investor_password("")` and `set_encryption_passphrase("")` would
have stored an empty value in the keychain. The CLI rejected empty
input before calling these setters, but the library did not — a
defence-in-depth gap reachable via programmatic misuse.

**Fix.** Both setters now raise `ValueError` on empty input. Patch
landed in commit `<TASK1_SHA>` (`src/mt5_pnl_exporter/secrets.py`).

### Finding 2 — `redact_filter` covers `logging` output only

`rich.Console` (`err.print` in `cli.py`) bypasses the filter. No
current `err.print` site interpolates a registered secret, so there is
no live leak. The risk is a future contributor adding an `err.print`
site without realising the filter would not catch it.

**Fix.** New `redact_filter.scrub(s: str) -> str` helper returns the
input with each registered secret replaced by `***`. Existing
`err.print` sites are audited and certified as clean; the helper is
available for any future site that needs to print a string possibly
containing a secret. Patch landed in commit `<TASK1_SHA>`
(`src/mt5_pnl_exporter/secrets.py`).

## Method

Grep used to enumerate sites:

```
git grep -n -E "keyring|passphrase|password|redact" -- 'src/**'
```

Criteria applied per site:

1. Does the site read or write a secret? If so, where does it travel
   afterwards?
2. Could the secret reach `stdout`, `stderr`, the filesystem, or a
   network call without passing through `redact_filter`?
3. Is the path under test?

Re-run this audit when adding any new keychain access, log output, or
`rich.Console` site.
````

- [ ] **Step 3: Render-check the audit doc**

```bash
cat docs/security-audit.md | jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' \
  | gh api /markdown --input - > /tmp/cycle3-audit-rendered.html
grep -c '<table' /tmp/cycle3-audit-rendered.html
grep -E -o '<h[1-6][^>]*>[^<]*' /tmp/cycle3-audit-rendered.html
```

Expected: `<table` count is `1`; headings include `Security audit — keychain reads, writes, and redaction boundaries`, `Sites`, `Findings`, `Finding 1 — ...`, `Finding 2 — ...`, and `Method`.

- [ ] **Step 4: Commit**

```bash
git add docs/security-audit.md
git commit -m "docs: keychain / redaction audit (2026-06-01)

Point-in-time audit of every keychain read/write and every site where
a keychain-sourced secret crosses a trust boundary. Eight rows: six
secret-touching sites plus two boundary helpers (redact_filter,
check_file_perms). Two findings from the walk-through, both fixed in
the prior commit:

- secrets.py setters accepted empty input (defence-in-depth gap)
- redact_filter only covers logging; rich.Console bypasses it

Closes item 8 of phase 1b parent spec."
```

Expected: commit lands on `phase-1b-cycle-3`.

---

## Task 4: Final verification, push, draft PR

**Files:** none modified.

- [ ] **Step 1: Full test suite**

```bash
uv run pytest
```

Expected: green, coverage ≥ 95%.

- [ ] **Step 2: Lint, format check, type check**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: all three clean.

- [ ] **Step 3: Schema staleness check**

The cycle 3 changes do not touch the schema, so the committed schema file should still match what the models generate.

```bash
uv run mt5-pnl-exporter schema && git diff --stat schema/snapshot.schema.json
```

Expected: no diff. If a diff appears, stop — something in cycle 3 unintentionally touched the snapshot models, which is out of scope.

- [ ] **Step 4: Review the branch shape**

```bash
git status
git log --oneline main..HEAD
```

Expected: working tree clean; three commits on the branch ahead of `main`:

```
<sha3> docs: keychain / redaction audit (2026-06-01)
<sha2> docs: threat model section + Windows-host reframe
<sha1> feat(secrets): empty-string guards + redact_filter.scrub helper
```

- [ ] **Step 5: Push the branch**

```bash
git push -u origin phase-1b-cycle-3
```

Expected: branch published; tracking origin/phase-1b-cycle-3.

- [ ] **Step 6: Open a draft PR**

```bash
gh pr create --draft --base main --head phase-1b-cycle-3 \
  --title "Phase 1b cycle 3: docs reframe, threat model, keychain audit" \
  --body "$(cat <<'EOF'
## Summary
- README gains a `## Threat model` section: trust boundary, what's protected, what isn't, transport guidance.
- README and CLAUDE.md replace "Windows VPS" framing with "the Windows host where MT5 runs". VPS is now one deployment choice among several, not the assumption.
- New `docs/security-audit.md` walks every keychain read/write and every site where a secret crosses a trust boundary; eight rows, two findings.
- Both findings fixed in `src/mt5_pnl_exporter/secrets.py`: empty-string guard on both setters; new `redact_filter.scrub(s)` helper for `rich.Console` output that bypasses the logging filter.

See [`docs/superpowers/specs/2026-06-01-phase-1b-cycle-3-design.md`](docs/superpowers/specs/2026-06-01-phase-1b-cycle-3-design.md)
and [`docs/superpowers/plans/2026-06-01-phase-1b-cycle-3.md`](docs/superpowers/plans/2026-06-01-phase-1b-cycle-3.md).

## Test plan
- [ ] `uv run pytest` passes with coverage ≥ 95%
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run ruff format --check src/ tests/` clean
- [ ] `uv run mypy src/mt5_pnl_exporter` clean
- [ ] `schema/snapshot.schema.json` unchanged
- [ ] README `## Threat model` renders correctly via `gh api /markdown`
- [ ] `docs/security-audit.md` renders correctly via `gh api /markdown`
EOF
)"
```

Expected: `gh pr create` returns a PR URL. Report the URL back to the user.

---

## Self-Review (completed before saving)

**Spec coverage:**

- Threat model section in README, ~300–400 words, structured as trust boundary → protected → not protected → transport guidance → Task 2 (Step 4).
- Windows-host reframe across README intro, install, quick-start heading → Task 2 (Steps 1–3).
- Windows-host reframe across CLAUDE.md intro, commands comment, gotcha → Task 2 (Steps 5–7).
- New `docs/security-audit.md` with preamble, eight-row table, two findings, method → Task 3 (Step 2).
- Empty-string guard on `set_investor_password` → Task 1 (Steps 2–5).
- Empty-string guard on `set_encryption_passphrase` → Task 1 (Steps 6–9).
- `redact_filter.scrub(s)` helper → Task 1 (Steps 10–13).
- Tests for both guards and all three scrub behaviours → Task 1 (Steps 2, 6, 10).
- Coverage stays ≥ 95% → Task 1 (Step 14), Task 4 (Step 1).
- Branch `phase-1b-cycle-3` from `main`, no direct pushes → Task 1 (Step 1), Task 4 (Steps 5–6).
- Plan ends with commit + push + draft PR → Task 4.
- No prior-spec edits required → confirmed in the spec's "Out of scope" section and not raised again here.

**Placeholder scan:**

- `<TASK1_SHA>` appears in Task 3 Step 2 only, and Task 3 Step 1 spells out how to retrieve and substitute it. Not a TBD — a deliberate substitution token.
- No "TODO", no "implement later", no "similar to Task N", no naked "add tests". Each code step shows the exact code; each command step shows the exact command and expected output.

**Type and naming consistency:**

- `set_investor_password(login: int, password: str) -> None` signature unchanged; only the body grows.
- `set_encryption_passphrase(passphrase: str) -> None` signature unchanged; only the body grows.
- `_RedactFilter.scrub(self, s: str) -> str` matches the spec's signature.
- Error messages match the test patterns: `"password cannot be empty"` and `"passphrase cannot be empty"`.
- `KEYRING_SERVICE` and `ENCRYPTION_PASSPHRASE_ACCOUNT` constants used as-is from the existing module.
- `re` is already imported at the top of `secrets.py`; no new imports beyond `pytest` in tests.
