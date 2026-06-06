# CLI Naming Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the CLI surface and a couple of internal/schema names so every name matches the tool's actual one-shot, manual behaviour, and document the tool as a manual on-demand exporter (no scheduling).

**Architecture:** This is a rename refactor, not new behaviour. Each task is one coherent rename applied across source, tests, and docs together, so the test suite stays green at every commit. No TDD "write a failing test first" — the behaviour is unchanged; the existing suite (100% coverage) is the safety net, and each task ends by running it.

**Tech Stack:** Python 3.12, `uv`, Typer, pydantic, pytest, ruff, mypy.

Spec: [`docs/superpowers/specs/2026-06-07-cli-naming-cleanup-design.md`](../specs/2026-06-07-cli-naming-cleanup-design.md)

---

## CRITICAL distinction — read before Task 1

There are **two** different `account_info` names in this codebase. Only one is ours:

- **OURS — rename it:** `DataSource.account_info(self, login)` — our protocol method (takes a `login`). Implementations: `sources/base.py`, `sources/mt5.py` (`MT5Source.account_info`), the fake `DataSource` in `tests/test_cli.py`, and all `src.account_info(...)` call sites in `tests/test_mt5_source.py`.
- **NOT OURS — leave it alone:** `MetaTrader5.account_info()` — the upstream MT5 API (no args). This appears as `self._mt5.account_info()` in `sources/mt5.py:221`, the fake MT5 module's `def account_info()` in `tests/test_mt5_source.py:65`/`fake.account_info = account_info` at line 75, and the error string `"account_info() returned None for ..."` (sources/mt5.py:223) plus its test match (`tests/test_mt5_source.py:638`). These describe the upstream API — **do not rename them.**

---

## File map

- `src/mt5_pnl_exporter/sources/base.py` — `DataSource` protocol method rename.
- `src/mt5_pnl_exporter/sources/mt5.py` — `MT5Source` method rename (our def only).
- `src/mt5_pnl_exporter/snapshot.py` — `last_success` → `last_success_at`; command names in error strings.
- `src/mt5_pnl_exporter/cli.py` — command renames, function names, help/docstring strings, log prefix, field name.
- `src/mt5_pnl_exporter/config.py` — command name in hint string + a comment.
- `schema/snapshot.schema.json` — regenerated.
- `tests/test_cli.py`, `tests/test_mt5_source.py`, `tests/test_snapshot.py`, `tests/test_config.py` — call sites, fake `DataSource`, match strings, test names.
- `README.md`, `CLAUDE.md` — docs.

---

## Task 1: Rename `DataSource.account_info` → `fetch_account_info`

Smallest, fully internal rename. No user-facing strings.

**Files:**
- Modify: `src/mt5_pnl_exporter/sources/base.py:48`
- Modify: `src/mt5_pnl_exporter/sources/mt5.py:219`
- Modify: `src/mt5_pnl_exporter/cli.py:94`
- Modify: `tests/test_cli.py` (fake `DataSource` def + spy)
- Modify: `tests/test_mt5_source.py` (our-method call sites + test name)

- [ ] **Step 1: Rename the protocol method**

In `src/mt5_pnl_exporter/sources/base.py:48`, change:
```python
    def account_info(self, login: int) -> AccountInfo: ...
```
to:
```python
    def fetch_account_info(self, login: int) -> AccountInfo: ...
```

- [ ] **Step 2: Rename the MT5Source implementation (our def only)**

In `src/mt5_pnl_exporter/sources/mt5.py:219`, change the method signature line:
```python
    def account_info(self, login: int) -> AccountInfo:
```
to:
```python
    def fetch_account_info(self, login: int) -> AccountInfo:
```
**Do NOT touch** `self._mt5.account_info()` (line 221) or the `"account_info() returned None for {login}"` string (line 223) — those are the upstream MT5 API.

- [ ] **Step 3: Update the cli.py call site**

In `src/mt5_pnl_exporter/cli.py:94`, change:
```python
            info = src.account_info(acct.login)
```
to:
```python
            info = src.fetch_account_info(acct.login)
```

- [ ] **Step 4: Update the fake DataSource and spy in test_cli.py**

In `tests/test_cli.py:59`, change `def account_info(self, login: int) -> AccountInfo:` to `def fetch_account_info(self, login: int) -> AccountInfo:`.

In `tests/test_cli.py` around lines 370-375 (the spy), change every `fake.account_info` / `original = fake.account_info` reference to `fake.fetch_account_info`. Concretely:
```python
    original = fake.fetch_account_info
    fake.fetch_account_info = lambda login: (calls.append(login), original(login))[1]  # type: ignore[assignment]
```

- [ ] **Step 5: Update our-method call sites in test_mt5_source.py**

Replace `src.account_info(` with `src.fetch_account_info(` at every call site (lines 149, 169, 170, 188, 201, 209, 222, 224, 639, 651). Rename the test function `test_account_info_raises_when_mt5_returns_none` → `test_fetch_account_info_raises_when_mt5_returns_none` (line 631).

**Leave untouched** in this file: `def account_info()` (line 65) and `fake.account_info = account_info` (line 75) — fake MT5 module; and the `match="account_info\\(\\) returned None for 514248"` string (line 638) — upstream API message.

- [ ] **Step 6: Run the suite and type/lint checks**

Run:
```bash
uv run pytest -q
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
```
Expected: all pass. Then confirm no stray references to our renamed method remain:
```bash
grep -rn "\.account_info(" src/ tests/ | grep -v "_mt5.account_info"
```
Expected: only `fetch_account_info` hits (no bare `.account_info(` other than `self._mt5.account_info()`).

- [ ] **Step 7: Commit**

```bash
git add src/mt5_pnl_exporter/sources/base.py src/mt5_pnl_exporter/sources/mt5.py src/mt5_pnl_exporter/cli.py tests/test_cli.py tests/test_mt5_source.py
git commit -m "refactor: rename DataSource.account_info to fetch_account_info"
```

---

## Task 2: Rename `AccountSnapshot.last_success` → `last_success_at`

Schema-model field rename; requires regenerating the JSON schema.

**Files:**
- Modify: `src/mt5_pnl_exporter/snapshot.py:48`
- Modify: `src/mt5_pnl_exporter/cli.py:109,129`
- Modify: `tests/test_snapshot.py:34`
- Modify: `tests/test_cli.py` (several)
- Regenerate: `schema/snapshot.schema.json`

- [ ] **Step 1: Rename the field on the model**

In `src/mt5_pnl_exporter/snapshot.py:48`, change `last_success: str | None` to `last_success_at: str | None`. Leave `last_error: str | None` unchanged.

- [ ] **Step 2: Update the cli.py construction sites**

In `src/mt5_pnl_exporter/cli.py`, the success path (line ~109):
```python
                    last_success_at=now.isoformat().replace("+00:00", "Z"),
```
and the carry-forward path (line ~129):
```python
                    last_success_at=prior_acct.last_success_at if prior_acct else None,
```

- [ ] **Step 3: Update tests that set or assert the field**

- `tests/test_snapshot.py:34` — `last_success="..."` → `last_success_at="..."`.
- `tests/test_cli.py` — replace `last_success=` with `last_success_at=` at the construction sites (lines ~206, ~215, ~264), and `.last_success` with `.last_success_at` at the assertion sites (lines ~238, ~239, ~243, ~299). Rename the test function `test_poll_carries_forward_last_success_on_failure` → `test_export_carries_forward_last_success_at_on_failure` (it will be re-touched in Task 3; renaming now is fine) and update its docstring text `last_success` → `last_success_at`.

- [ ] **Step 4: Regenerate the schema**

Run:
```bash
uv run mt5-pnl-exporter schema
```
Expected: `Wrote schema/snapshot.schema.json`. The regenerated file should now contain `last_success_at` and no `last_success`.

- [ ] **Step 5: Run the suite + checks**

Run:
```bash
uv run pytest -q
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
```
Expected: all pass — including `tests/test_schema_file.py` (it fails if the schema on disk drifts; regenerating in Step 4 keeps it in sync). Confirm:
```bash
grep -rn "last_success\b" src/ tests/ schema/
```
Expected: no matches (only `last_success_at`).

- [ ] **Step 6: Commit**

```bash
git add src/mt5_pnl_exporter/snapshot.py src/mt5_pnl_exporter/cli.py tests/test_snapshot.py tests/test_cli.py schema/snapshot.schema.json
git commit -m "refactor: rename last_success field to last_success_at"
```

---

## Task 3: Rename the `poll` command → `export`

**Files:**
- Modify: `src/mt5_pnl_exporter/cli.py` (def, header docstring, help, log prefix)
- Modify: `src/mt5_pnl_exporter/snapshot.py:160,174,181` (hint strings)
- Modify: `src/mt5_pnl_exporter/config.py:51` (comment)
- Modify: `tests/test_cli.py` (invocations + test names), `tests/test_snapshot.py:267` (match)

- [ ] **Step 1: Rename the command function**

In `src/mt5_pnl_exporter/cli.py`, the command at line 47-48 is `@app.command()` then `def poll(`. Rename the function to `export`:
```python
@app.command()
def export(
```
Typer derives the command name from the function name, so this makes the command `export`. (No decorator argument needed.)

- [ ] **Step 2: Update cli.py strings and log prefix**

- Module header docstring (line 1):
```python
"""mt5-pnl-exporter CLI — export | set-password | schema"""
```
(the `set-password` part is fixed in Task 4.)
- App help (line 34):
```python
    help="MT5 P&L exporter — export deal history, write snapshot.json.gz.age.",
```
- The function docstring (was "Fetch deal history + open positions from MT5 and write ..."): leave the wording, it's still accurate.
- Replace the `[poll]` log prefix with `[export]` in every log call in this function (the `log.info`/`log.error` messages around lines 113-120, 136-139, 151). For example:
```python
            log.info(
                f"[export] {acct.label} ({acct.login}): "
                f"{len(deals)} closed deals, {len(positions)} open, "
                f"{len(flows)} cash flows  OK"
            )
```
Apply the same `[poll]` → `[export]` swap to the failure log, the "All N accounts failed" log, and the "wrote {snap_path}" log.

- [ ] **Step 3: Update user-facing hint strings that name `poll`**

- `src/mt5_pnl_exporter/snapshot.py:160`: `"Run 'mt5-pnl-exporter poll' on the Windows host first to generate it."` → `"Run 'mt5-pnl-exporter export' on the Windows host first to generate it."`
- `src/mt5_pnl_exporter/snapshot.py:174`: `"Snapshot file is corrupt at {path}; re-run 'mt5-pnl-exporter poll' to regenerate."` → `... re-run 'mt5-pnl-exporter export' to regenerate."`
- `src/mt5_pnl_exporter/snapshot.py:181`: `"Upgrade mt5-pnl-exporter, or re-run 'poll' on a compatible host."` → `"... or re-run 'export' on a compatible host."`
- `src/mt5_pnl_exporter/config.py:51`: comment `"""Warn if config has group/other-readable bits. Only call from poll."""` → `"... Only call from export."`

- [ ] **Step 4: Update tests**

- `tests/test_cli.py`: replace every `runner.invoke(app, ["poll", ...])` with `["export", ...]` (lines 159, 173, 230, 279, 293, 307, 323, 375). Rename the affected test functions for clarity, e.g. `test_poll_*` → `test_export_*`.
- `tests/test_snapshot.py:267`: `with pytest.raises(FileNotFoundError, match="poll"):` → `match="export"`.
- After editing, grep the test dir for any assertion on the `[poll]` log prefix and update to `[export]`:
```bash
grep -rn "\[poll\]\|\"poll\"\|'poll'" tests/
```
Update any hits to `export`.

- [ ] **Step 5: Run the suite + checks**

Run:
```bash
uv run pytest -q
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
```
Expected: all pass. Confirm the command works and the old name is gone:
```bash
uv run mt5-pnl-exporter --help        # should list 'export', not 'poll'
grep -rn "\bpoll\b" src/ | grep -vi "poll until\|polls"
```
Expected `--help` shows `export`; the grep shows no command-name references (the `# poll until` comment in mt5.py:20 about history sync is about waiting/looping, not the command — leave it).

- [ ] **Step 6: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py src/mt5_pnl_exporter/snapshot.py src/mt5_pnl_exporter/config.py tests/test_cli.py tests/test_snapshot.py
git commit -m "refactor: rename poll command to export"
```

---

## Task 4: Rename `set-password` command → `set-investor-password`

**Files:**
- Modify: `src/mt5_pnl_exporter/cli.py:1,159,160`
- Modify: `src/mt5_pnl_exporter/config.py:91`
- Modify: `tests/test_cli.py` (invocations + names), `tests/test_config.py:164` (match)

- [ ] **Step 1: Rename the command and its function**

In `src/mt5_pnl_exporter/cli.py`, the command at lines 159-162 is:
```python
@app.command("set-password")
def set_password(
    login: Annotated[int, typer.Argument(help="MT5 account login number")],
) -> None:
```
Change to (note the function rename to `set_investor_password_cmd`, mirroring the existing `set_encryption_passphrase_cmd`; this avoids colliding with the imported `set_investor_password` from `secrets`):
```python
@app.command("set-investor-password")
def set_investor_password_cmd(
    login: Annotated[int, typer.Argument(help="MT5 account login number")],
) -> None:
```
The body already calls the imported `set_investor_password(login, pw)` — leave the body unchanged.

- [ ] **Step 2: Update the cli.py header docstring**

Line 1 is now `"""mt5-pnl-exporter CLI — export | set-password | schema"""`; change to:
```python
"""mt5-pnl-exporter CLI — export | set-investor-password | set-encryption-passphrase | schema"""
```

- [ ] **Step 3: Update the config.py hint string**

`src/mt5_pnl_exporter/config.py:91`:
```python
            + "\nRun: mt5-pnl-exporter set-investor-password <login>"
```

- [ ] **Step 4: Update tests**

- `tests/test_cli.py`: `runner.invoke(app, ["set-password", "1234567"], ...)` → `["set-investor-password", "1234567"]` (lines 332, 344). Rename `test_set_password_empty_exits_nonzero` → `test_set_investor_password_empty_exits_nonzero` and `test_set_password_stores_password` → `test_set_investor_password_stores_password`. Update the section comment at line 328.
- `tests/test_config.py:164`: `pytest.raises(RuntimeError, match="set-password")` → `match="set-investor-password"`.

- [ ] **Step 5: Run the suite + checks**

Run:
```bash
uv run pytest -q
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
```
Expected: all pass. Confirm:
```bash
uv run mt5-pnl-exporter --help        # lists 'set-investor-password'
grep -rn "set-password" src/ tests/
```
Expected: `--help` shows `set-investor-password`; grep returns nothing.

- [ ] **Step 6: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py src/mt5_pnl_exporter/config.py tests/test_cli.py tests/test_config.py
git commit -m "refactor: rename set-password command to set-investor-password"
```

---

## Task 5: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the intro and command references**

- Line 3: `... CLI (`mt5-pnl-exporter`) that polls MT5 deal history ...` → `... CLI (`mt5-pnl-exporter`) that exports MT5 deal history on demand ...`.
- Commands block (line ~16): `uv run mt5-pnl-exporter poll` → `uv run mt5-pnl-exporter export                 # run a real export (Windows + creds)`.
- Architecture (line 25): `commands: `poll`, `set-password`, `set-encryption-passphrase`, `schema`.` → `commands: `export`, `set-investor-password`, `set-encryption-passphrase`, `schema`.`
- Gotchas line 35: `... enforced by `poll` only.` → `... enforced by `export` only.`
- Gotchas line 36: `... `poll` refuses to run if it's unset ...` → `... `export` refuses to run if it's unset ...`.

- [ ] **Step 2: Add a "manual, no scheduling" gotcha**

Add a new bullet to the Gotchas section:
```markdown
- **`export` is one-shot and manual.** It fetches once and exits — there is no
  polling loop or daemon. v1 is run-on-demand by design; no scheduler recipe
  ships (a low-frequency schedule would only serve stale equity/open positions
  by viewing time). If scheduling is ever added, a Windows Task Scheduler task
  must run as the same user that holds the keychain entries, in "run only when
  logged on" mode, or `keyring` can't read the credential vault.
```

- [ ] **Step 3: Verify and commit**

Run:
```bash
grep -rn "\bpoll\b\|set-password" CLAUDE.md
```
Expected: no command-name hits. Then:
```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for export rename and manual-only v1"
```

---

## Task 6: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the quick-start block**

In the `## Quick start` fenced block (lines ~56-68):
- `$ mt5-pnl-exporter set-password 1234567` → `$ mt5-pnl-exporter set-investor-password 1234567`.
- `$ mt5-pnl-exporter poll` → `$ mt5-pnl-exporter export`.
- The sample log lines `[INFO] [poll] ...` (lines 66-68) → `[INFO] [export] ...`.

- [ ] **Step 2: Update the Commands list**

Lines 113-114:
```markdown
- `mt5-pnl-exporter export` — fetch deals from MT5 once and write `snapshot.json.gz.age` atomically.
- `mt5-pnl-exporter set-investor-password <login>` — store an investor password in the OS keychain (`keyring`).
```

- [ ] **Step 3: Update remaining prose references**

- Line 134: ``... `poll` warns when the file is ...`` → ``... `export` warns when the file is ...``; and ``... via `set-password` and `set-encryption-passphrase` ...`` → ``... via `set-investor-password` and `set-encryption-passphrase` ...``.
- Line 144: `` `poll` logs into each account ...`` → `` `export` logs into each account ...``; and `... auto-backfills on the next tick.` → `... auto-backfills on the next run.` (the tool is manual, so "tick" is misleading).
- Line 158: `Each `poll` gzips the JSON ...` → `Each `export` gzips the JSON ...`.
- Line 162: `... can read the keychain, run `poll`, and read decrypted snapshots.` → `... run `export`, ...`.
- Line 172: `... whether a poll ran today are visible ...` → `... whether an export ran today are visible ...`.
- Line 173: `... re-run `poll` to rebuild it ...` → `... re-run `export` to rebuild it ...`.

- [ ] **Step 4: Confirm no scheduling section was added and the old names are gone**

Run:
```bash
grep -rin "task scheduler\|schtasks\|scheduled task" README.md   # expect: nothing
grep -rn "\bpoll\b\|set-password" README.md                       # expect: nothing
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README for export rename and manual on-demand framing"
```

---

## Task 7: Final whole-repo verification

**Files:** none (verification only).

- [ ] **Step 1: Full green check**

Run:
```bash
uv run pytest                       # 100% coverage incl. schema-staleness check
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
```
Expected: all pass, coverage 100%.

- [ ] **Step 2: Confirm no lingering old names anywhere**

Run:
```bash
grep -rn "set-password\|last_success\b" src/ tests/ README.md CLAUDE.md schema/
grep -rn "\.account_info(" src/ tests/ | grep -v "_mt5.account_info"
grep -rni "\bpoll\b" src/ README.md CLAUDE.md | grep -vi "poll until\|polls\b"
```
Expected: first two return nothing; the third returns nothing meaningful (only the `# poll until` history-sync comment in `sources/mt5.py`, which is about waiting and is intentionally kept).

- [ ] **Step 3: Smoke-test the CLI help**

Run:
```bash
uv run mt5-pnl-exporter --help
```
Expected: commands listed are `export`, `set-investor-password`, `set-encryption-passphrase`, `schema`.

---

## Self-review notes (author)

- **Spec coverage:** A=Tasks 3-4; B=Task 1; C=Task 2; D (keep-as-is) enforced by the targeted greps in Tasks 1/3 and Task 7; manual-export framing = Tasks 5-6. All spec sections covered.
- **The `account_info` trap** (our method vs the MT5 API) is called out up front and re-flagged in Task 1 to prevent renaming the wrong symbol.
- **Function-name collision** avoided: `set_password` → `set_investor_password_cmd` (not `set_investor_password`, which is the imported keyring helper).
- **Schema staleness:** Task 2 regenerates `schema/snapshot.schema.json`; `tests/test_schema_file.py` guards it.
