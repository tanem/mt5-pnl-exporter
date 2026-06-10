# Export Prior-Read Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `export` tolerate an existing-but-unreadable prior snapshot (wrong passphrase, corrupt, or unsupported schema) by warning and regenerating instead of crashing.

**Architecture:** Add an `except ValueError` branch beside the existing `except FileNotFoundError` at the prior-read call site in `cli.export`. An unreadable prior is treated as absent — `prior_by_login` stays empty, so the rest of `export` already does the right thing (empty carry-forward; the all-fail branch is false, so the freshly-built snapshot is written). Resilience lives at the call site; `snapshot.read()` stays strict.

**Tech Stack:** Python 3.12, Typer CLI, pytest (`CliRunner` + in-test fake `DataSource`), `pyrage`/gzip snapshot pipeline.

**Spec:** [`docs/superpowers/specs/2026-06-11-export-prior-read-resilience-design.md`](../specs/2026-06-11-export-prior-read-resilience-design.md)

---

## File Structure

- `src/mt5_pnl_exporter/cli.py` — add the `except ValueError` branch in `export` (currently `cli.py:80-84`). Single responsibility unchanged.
- `tests/test_cli.py` — two new tests in the existing "export error handling" area, using the established `_FakeSource` / `install_fake` / `_write_cfg` / `TEST_PASSPHRASE` harness. Adds `import logging` for `caplog` level control.
- `CLAUDE.md` — one new gotcha bullet documenting the behaviour.

No new files. No schema change.

---

### Task 1: Tolerate an unreadable prior snapshot (TDD)

**Files:**
- Modify: `tests/test_cli.py` (add `import logging`; add one test after the existing `test_export_writes_errors_when_all_fail_no_prior`)
- Modify: `src/mt5_pnl_exporter/cli.py:80-84`

- [ ] **Step 1: Add `import logging` to the test module**

At the top of `tests/test_cli.py`, the imports currently begin:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
```

Add `import logging` so the block reads:

```python
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_cli.py` (after `test_export_writes_errors_when_all_fail_no_prior`, which ends around line 299):

```python
def test_export_regenerates_when_prior_unreadable(tmp_path, install_fake, caplog):
    """An existing prior that can't be decrypted is treated as absent: warn and regenerate."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Trend EA", 1234567), ("Scalper EA", 7654321)])
    os.chmod(cfg_path, 0o600)

    # Plant an undecryptable prior (garbage bytes -> pyrage.DecryptError -> ValueError in read()).
    snap_path.write_bytes(b"not a valid age file")

    install_fake(_fake_from_sample())

    with caplog.at_level(logging.WARNING, logger="mt5_pnl_exporter.cli"):
        result = runner.invoke(app, ["export", "--config", str(cfg_path)])

    assert result.exit_code == 0, result.output
    # The garbage file was overwritten with a real, decryptable snapshot.
    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    assert {a.login for a in snap.accounts} == {1234567, 7654321}
    # A warning explained why the prior was ignored.
    assert "Could not read prior snapshot" in caplog.text
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_export_regenerates_when_prior_unreadable -v`
Expected: FAIL — `export` currently raises an uncaught `ValueError` from `snapshot.read`, so `CliRunner` records a non-zero exit and `result.exit_code == 0` fails (the exception is the planted-garbage decrypt failure).

- [ ] **Step 4: Implement the fix**

In `src/mt5_pnl_exporter/cli.py`, the prior-read block currently reads:

```python
    prior_by_login: dict[int, AccountSnapshot] = {}
    try:
        prior = snapshot.read(snap_path, encryption_passphrase)
        prior_by_login = {a.login: a for a in prior.accounts}
    except FileNotFoundError:
        pass
```

Replace it with:

```python
    prior_by_login: dict[int, AccountSnapshot] = {}
    try:
        prior = snapshot.read(snap_path, encryption_passphrase)
        prior_by_login = {a.login: a for a in prior.accounts}
    except FileNotFoundError:
        pass
    except ValueError as exc:
        log.warning(
            f"[export] Could not read prior snapshot at {snap_path} ({exc}); "
            "treating as absent and regenerating."
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_export_regenerates_when_prior_unreadable -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix: tolerate unreadable prior snapshot in export

read() raises ValueError when an existing snapshot can't be decrypted
(wrong passphrase, corrupt, or unsupported schema). export only caught
FileNotFoundError, so a passphrase change bricked every subsequent run.
Catch ValueError too: warn, treat the prior as absent, and regenerate.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Regression test — all accounts fail with an unreadable prior

This characterises the documented consequence: when the prior is unreadable *and* every account fails, the all-error snapshot overwrites the garbage file (rather than the "keep previous snapshot" branch firing, which requires a non-empty `prior_by_login`). It exercises the same `except ValueError` branch from Task 1, so it passes without new production code — that is expected; it guards the behaviour against future regressions.

**Files:**
- Modify: `tests/test_cli.py` (add one test)

- [ ] **Step 1: Add the test**

Append to `tests/test_cli.py` (after the test from Task 1):

```python
def test_export_overwrites_unreadable_prior_when_all_fail(tmp_path, install_fake):
    """Unreadable prior + all accounts fail: the all-error snapshot replaces the garbage file."""
    cfg_path = tmp_path / "config.yaml"
    snap_path = tmp_path / "snapshot.json.gz.age"
    _write_cfg(cfg_path, str(snap_path), [("Bad", 99998)])
    os.chmod(cfg_path, 0o600)

    snap_path.write_bytes(b"not a valid age file")

    fake = _FakeSource(fail_logins={99998})
    install_fake(fake)

    result = runner.invoke(app, ["export", "--config", str(cfg_path)])

    assert result.exit_code == 1
    # The garbage prior was unreadable, so it was overwritten with a readable all-error snapshot.
    snap = snapshot.read(snap_path, TEST_PASSPHRASE)
    assert len(snap.accounts) == 1
    assert snap.accounts[0].last_error is not None
    assert snap.accounts[0].last_success_at is None
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_export_overwrites_unreadable_prior_when_all_fail -v`
Expected: PASS (behaviour provided by Task 1's change; this test documents and locks it in).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "$(cat <<'EOF'
test: lock in overwrite-on-all-fail with unreadable prior

When the prior snapshot can't be decoded and every account also fails,
the all-error snapshot replaces the unreadable file rather than the
keep-previous branch firing. Characterisation test for that consequence.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Document the behaviour in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (the "## Gotchas" bullet list)

- [ ] **Step 1: Add the gotcha bullet**

In `CLAUDE.md`, find the existing bullet about the snapshot being mandatorily encrypted:

```markdown
- **Snapshot is mandatorily age-encrypted** with a keychain-stored passphrase (account `encryption-passphrase` on `KEYRING_SERVICE`). `snapshot.read()` and `snapshot.write()` both require the passphrase; `export` refuses to run if it's unset (`set-encryption-passphrase` first). Consumers must reverse the same `gzip → age` pipeline.
```

Immediately after that bullet, add:

```markdown
- **`export` tolerates an unreadable prior snapshot.** It reads the existing snapshot first (to carry account data forward and to decide whether to keep the previous file when all accounts fail). If that file is missing *or* can't be decoded (wrong passphrase after a `set-encryption-passphrase` change, corrupt, or unsupported schema), `export` logs a warning and regenerates rather than crashing — the prior read is only an optimisation. It catches both `FileNotFoundError` and `ValueError` at the call site; `snapshot.read()` itself stays strict.
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "tolerates an unreadable prior" CLAUDE.md`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: note export's unreadable-prior tolerance in CLAUDE.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Full verification

**Files:** none (read-only checks).

- [ ] **Step 1: Run the full suite with coverage**

Run: `uv run pytest`
Expected: PASS, 100% coverage maintained. Both new `except ValueError` branch lines (the branch and the `log.warning` call) are exercised by the two new tests.

- [ ] **Step 2: Lint and type-check**

Run: `uv run ruff check src/ tests/` and `uv run mypy src/mt5_pnl_exporter`
Expected: both clean, no findings.

- [ ] **Step 3: Confirm change scope**

Run: `git diff main --stat`
Expected: only `src/mt5_pnl_exporter/cli.py`, `tests/test_cli.py`, `CLAUDE.md`, and the spec/plan docs under `docs/superpowers/` appear. No `schema/` change.

---

## Self-Review

**Spec coverage:**
- "Catch `ValueError` beside `FileNotFoundError`; warn; treat prior as absent" → Task 1, step 4. ✓
- "`log.warning`, message names the file and interpolates the cause" → Task 1, step 4 (message includes `{snap_path}` and `{exc}`). ✓
- "Test: regenerate on unreadable prior (succeeding account), exit 0, file readable, warning emitted" → Task 1, step 2. ✓
- "Test: overwrite-on-all-fail consequence, exit 1, readable all-error snapshot" → Task 2, step 1. ✓
- "Catch `ValueError` specifically, not bare `Exception`" → Task 1 implementation uses `except ValueError`. ✓
- "No `snapshot.read()` change; no schema change" → not modified; Task 4 step 3 confirms. ✓
- "CLAUDE.md gotcha; no README change" → Task 3; README untouched. ✓
- "100% coverage holds" → Task 4, step 1. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases". Every code step shows complete code.

**Type consistency:** `prior_by_login: dict[int, AccountSnapshot]`, `snapshot.read(snap_path, encryption_passphrase)`, `log` (the `logging.getLogger(__name__)` bound in `export`), and test helpers (`_FakeSource`, `_fake_from_sample`, `install_fake`, `_write_cfg`, `runner`, `TEST_PASSPHRASE`) all match the existing `cli.py` and `tests/test_cli.py` definitions. The fake-failure path (`_FakeSource(fail_logins={99998})`) mirrors the existing `test_export_keeps_prior_snapshot_when_all_fail`.
