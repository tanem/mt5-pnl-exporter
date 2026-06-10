# Snapshot Verification Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give contributors and consumers a copy-pasteable way to decode and verify `snapshot.json.gz.age`, closing the gap where the docs describe the encryption pipeline but show no runnable command.

**Architecture:** Two additive documentation edits, no code/schema/behaviour change. CONTRIBUTING gains a verification step that round-trips a real export through the project's own `snapshot.read()` path; README gains a language-agnostic `age` CLI decode snippet next to the existing pipeline description, with a one-line "it's ciphertext, you can't open it directly" caveat.

**Tech Stack:** Markdown only (`README.md`, `CONTRIBUTING.md`). Verification uses `grep`, the `age` CLI, and the existing `mt5-pnl-exporter` package.

**Spec:** [`docs/superpowers/specs/2026-06-10-snapshot-verification-docs-design.md`](../specs/2026-06-10-snapshot-verification-docs-design.md)

---

## File Structure

- `CONTRIBUTING.md` — append step 6 to "Smoke-test a real export" (after line 40); update the "Steps 2–5" lead-in (line 42) to "Steps 2–6".
- `README.md` — insert the consumer decode snippet immediately after the pipeline sentence in "How it works" (after line 177).

No new files. No `CLAUDE.md` edit (this is not a command/architecture/gotcha change).

---

### Task 1: CONTRIBUTING — add the verification step

**Files:**
- Modify: `CONTRIBUTING.md:40-42`

- [ ] **Step 1: Insert step 6 after the current step 5**

Find this block (lines 40–42):

```markdown
5. `uv run mt5-pnl-exporter export` — confirm it logs `OK` per account and writes the snapshot.

Steps 2–5 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point, the `[mt5]` extra, the bundled schema file), build and install the wheel before publishing:
```

Replace it with (adds step 6; changes "Steps 2–5" to "Steps 2–6"):

````markdown
5. `uv run mt5-pnl-exporter export` — confirm it logs `OK` per account and writes the snapshot.
6. Verify the snapshot decrypts and validates — this exercises the same `age → gzip → JSON` read path a consumer uses. The on-disk file is ciphertext, so opening it directly won't work; read it back via the API:

   ```bash
   uv run python -c "from pathlib import Path; import mt5_pnl_exporter.snapshot as s, mt5_pnl_exporter.secrets as sec; snap = s.read(Path('<snapshot_path>'), sec.get_encryption_passphrase()); print(snap.generated_at, '|', len(snap.closed_deals), 'deals,', len(snap.open_positions), 'open,', len(snap.cash_flows), 'cash flows'); [print(a.login, a.label, a.balance, a.equity) for a in snap.accounts]"
   ```

   Replace `<snapshot_path>` with your configured `snapshot_path`. If it prints without raising, the file is structurally sound — `read()` reverses the pipeline and validates the full pydantic model.

Steps 2–6 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point, the `[mt5]` extra, the bundled schema file), build and install the wheel before publishing:
````

- [ ] **Step 2: Verify the edit**

Run: `grep -n "Steps 2–6\|Verify the snapshot decrypts\|get_encryption_passphrase" CONTRIBUTING.md`
Expected: three matches — the updated lead-in, the new step-6 heading, and the one-liner. Confirm no remaining "Steps 2–5" in the file: `grep -n "Steps 2–5" CONTRIBUTING.md` returns nothing.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "$(cat <<'EOF'
docs: add snapshot verification step to smoke test

Step 6 reads a freshly-exported snapshot back through snapshot.read(),
confirming the artifact round-trips (not just that export ran) and
exercising the same age → gzip → JSON path a consumer uses.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: README — add the consumer decode snippet

**Files:**
- Modify: `README.md:177`

- [ ] **Step 1: Insert the decode snippet after the pipeline sentence**

Find this line (line 177, in the "How it works" section):

```markdown
Gzip + `age` encryption is mandatory, not optional. The on-disk file is always `snapshot.json.gz.age`; readers must reverse the pipeline (`age decrypt → gunzip → json.loads`) to decrypt. Sync services (Dropbox, OneDrive, Syncthing) and backups only ever see ciphertext.
```

Insert immediately after it (new blank line, then the snippet):

````markdown
The on-disk file is ciphertext — you can't open it directly (double-clicking a `.age` file just fails). To read it, reverse the pipeline. With the [age](https://age-encryption.org/) CLI installed (`brew install age` on macOS; see the age site for other platforms):

```bash
age -d mt5.json.gz.age | gunzip     # prompts for the passphrase, prints the JSON
```
````

- [ ] **Step 2: Verify the edit**

Run: `grep -n "age -d mt5.json.gz.age\|can't open it directly\|brew install age" README.md`
Expected: three matches, all within the "How it works" section (immediately after the line ending "only ever see ciphertext").

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: show how to decode the encrypted snapshot

Add a language-agnostic `age -d | gunzip` snippet next to the pipeline
description, with a one-line caveat naming the "can't open .age directly"
dead-end. Install guidance is one example plus the upstream link, not a
per-OS matrix.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Final verification

**Files:** none (read-only checks).

- [ ] **Step 1: Confirm docs-only — no code/schema touched**

Run: `git diff main --stat`
Expected: only `CONTRIBUTING.md`, `README.md`, and the two spec/plan files under `docs/superpowers/` appear. No files under `src/`, `tests/`, or `schema/`.

- [ ] **Step 2: Confirm the test suite is unaffected**

Run: `uv run pytest -q`
Expected: PASS (docs-only change; nothing in the suite depends on these files).

- [ ] **Step 3 (host-dependent — run where possible, note if skipped): live decode checks**

On the Windows host mid-smoke-test, run the CONTRIBUTING step-6 one-liner against the real snapshot (substituting the real `snapshot_path`):
Expected: prints `generated_at | N deals, N open, N cash flows` then one line per account, without raising.

On a host with the `age` CLI installed (e.g. macOS after `brew install age`), run `age -d mt5.json.gz.age | gunzip`:
Expected: prompts `Enter passphrase:`, then prints the snapshot JSON to stdout.

If either host isn't available in this session, note it as skipped rather than marking it done.

---

## Self-Review

**Spec coverage:**
- "Contributor verification step via `snapshot.read()`" → Task 1. ✓
- "Consumer language-agnostic decode command" → Task 2. ✓
- "One-line ciphertext caveat" → Task 2, step 1. ✓
- "`age -d` no `-p` on decrypt" → Task 2 snippet uses `age -d` with no `-p`. ✓
- "Install guidance = link + one example, not a matrix" → Task 2 snippet. ✓
- "No `CLAUDE.md` change" → File Structure note; Task 3 confirms docs-only. ✓
- "Verification: live decode on Windows + age CLI" → Task 3, step 3. ✓

**Placeholder scan:** `<snapshot_path>` is the only placeholder; it is intentional and the step tells the engineer to substitute the configured `snapshot_path`. No TBD/TODO/"handle edge cases".

**Type consistency:** Function names match the source — `snapshot.read(path, passphrase)` and `secrets.get_encryption_passphrase()` (verified against `src/mt5_pnl_exporter/snapshot.py` and `secrets.py`). `age -d` (no `-p`) is the correct decrypt invocation.
