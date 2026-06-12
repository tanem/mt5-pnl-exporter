# Config path expansion + curated error UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `~` in `snapshot_path` at config-load time, and make `export` print its curated one-liners (missing config, missing keyring passwords) instead of raw tracebacks — while ensuring crashes never dump secrets via Typer's locals-rendering pretty exceptions.

**Architecture:** A pydantic `field_validator` on `Config.snapshot_path` runs `Path.expanduser()` once at load, so every consumer sees the resolved path. `check_file_perms` early-returns on a missing file so `load_config` can raise its curated `FileNotFoundError`; `export` catches that and the `RuntimeError` from `resolve_passwords` in two narrow try blocks, printing via the existing `err` console. `typer.Typer(pretty_exceptions_enable=False)` closes the secrets-in-crash-locals leak.

**Tech Stack:** Python 3.12, pydantic v2, Typer, pytest (100% branch coverage enforced), ruff, mypy strict. All commands run via `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-12-config-path-and-error-ux-design.md`

**Branch:** `fix/config-path-and-error-ux` (already created; spec committed on it).

---

### Task 1: `snapshot_path` tilde expansion

**Files:**
- Modify: `src/mt5_pnl_exporter/config.py` (Config model, after `_terminal_path_none_to_empty`, ~line 33)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`, after `test_terminal_path_null_coerced_to_empty` (~line 72). `Path` and the `_write_cfg` helper are already imported/defined in this file.

```python
def test_snapshot_path_tilde_expands_to_home(tmp_path, monkeypatch):
    """`~/...` in snapshot_path resolves against the user's home at load time."""
    monkeypatch.setenv("HOME", str(tmp_path))  # POSIX
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: ~/snaps/mt5.json.gz.age\n"
        "accounts:\n"
        "  - label: Test\n"
        "    login: 1\n"
        "    server: TestBroker\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.snapshot_path == str(tmp_path / "snaps" / "mt5.json.gz.age")
    assert "~" not in cfg.snapshot_path


def test_snapshot_path_absolute_unchanged():
    """Absolute paths pass through the expansion validator untouched."""
    cfg = Config(
        snapshot_path="/abs/s.json",
        accounts=[AccountConfig(label="A", login=1, server="X")],
    )
    assert cfg.snapshot_path == "/abs/s.json"
```

- [ ] **Step 2: Run the tests to verify the tilde one fails**

Run: `uv run pytest tests/test_config.py -k snapshot_path -v --no-cov`
Expected: `test_snapshot_path_tilde_expands_to_home` FAILS (assert `'~/snaps/...' == '/tmp/.../snaps/...'` — no expansion yet); `test_snapshot_path_absolute_unchanged` PASSES (it is a regression guard).

Note: `--no-cov` because a partial run can't meet the 100% gate; the gate is enforced on full runs.

- [ ] **Step 3: Implement the validator**

In `src/mt5_pnl_exporter/config.py`, inside `Config`, directly after `_terminal_path_none_to_empty` (after ~line 33; `Path` is already imported, and `field_validator` is already in the pydantic import):

```python
    @field_validator("snapshot_path")
    @classmethod
    def _snapshot_path_expand_user(cls, v: str) -> str:
        return str(Path(v).expanduser())
```

- [ ] **Step 4: Run the full suite to verify green + coverage holds**

Run: `uv run pytest`
Expected: all tests PASS, coverage 100% (the gate fails the run otherwise).

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/config.py tests/test_config.py
git commit -m "fix: expand ~ in snapshot_path at config load

Path(cfg.snapshot_path) never ran expanduser, so the documented
~/snapshots/... example created a literal '~' directory under the CWD.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `check_file_perms` early return on missing file

**Files:**
- Modify: `src/mt5_pnl_exporter/config.py:50-61` (`check_file_perms`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`, after `test_check_file_perms_skipped_on_windows` (~line 135):

```python
def test_check_file_perms_missing_file_is_noop(tmp_path, capsys):
    """A missing config is load_config's problem (curated error), not a stat() crash."""
    check_file_perms(tmp_path / "nope.yaml")
    assert capsys.readouterr().err == ""
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_check_file_perms_missing_file_is_noop -v --no-cov`
Expected: FAIL with `FileNotFoundError` from `path.stat()`.

- [ ] **Step 3: Implement the early return**

In `src/mt5_pnl_exporter/config.py`, `check_file_perms`, after the `os.name == "nt"` guard and before the `stat()` call:

```python
    if not path.exists():
        return  # load_config raises the curated FileNotFoundError
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: all tests PASS, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/config.py tests/test_config.py
git commit -m "fix: check_file_perms no-ops when the config file is absent

Lets load_config raise its curated 'copy config.example.yaml' error
instead of a bare FileNotFoundError from stat().

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: curated errors in `export` + no pretty exceptions

**Files:**
- Modify: `src/mt5_pnl_exporter/cli.py:33-36` (Typer app), `cli.py:56-57` (config load), `cli.py:71` (resolve_passwords)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Tighten the existing missing-config test and add the missing-password test**

In `tests/test_cli.py`, replace `test_export_config_not_found` (~line 356) with:

```python
def test_export_config_not_found(tmp_path):
    """Missing config: curated 'copy the example' message, exit 1, no traceback."""
    missing = tmp_path / "nonexistent.yaml"
    result = runner.invoke(app, ["export", "--config", str(missing)])
    assert result.exit_code == 1
    assert "config.example.yaml" in result.output
    assert "Traceback" not in result.output
```

Below it, add (uses the module's existing `TEST_PASSPHRASE`, `_write_cfg`, `os`, `runner`, `app`; no `install_fake` — the real `resolve_passwords` must run and fail before `MT5Source` is constructed):

```python
def test_export_missing_investor_password_curated_error(tmp_path, monkeypatch):
    """Missing keyring password: curated hint, exit 1, no traceback."""
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json.gz.age"), [("Trend EA", 1234567)])
    os.chmod(cfg_path, 0o600)
    monkeypatch.setattr(
        "mt5_pnl_exporter.cli.get_encryption_passphrase", lambda: TEST_PASSPHRASE
    )
    # Real resolve_passwords runs; the keyring lookup it makes finds nothing.
    monkeypatch.setattr("mt5_pnl_exporter.config.get_investor_password", lambda login: None)

    result = runner.invoke(app, ["export", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert "set-investor-password" in result.output
    assert "Traceback" not in result.output
```

- [ ] **Step 2: Run both tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_export_config_not_found tests/test_cli.py::test_export_missing_investor_password_curated_error -v --no-cov`
Expected: both FAIL on the output-contains assertions (the exceptions currently propagate uncaught, so nothing curated is printed).

- [ ] **Step 3: Implement the cli.py changes**

Three edits in `src/mt5_pnl_exporter/cli.py`.

(a) Disable pretty exceptions on the app (~line 33):

```python
app = typer.Typer(
    help="MT5 P&L exporter — export deal history, write snapshot.json.gz.age.",
    add_completion=False,
    pretty_exceptions_enable=False,
)
```

(b) Wrap the config load (replaces lines 56-57):

```python
    try:
        check_file_perms(config_path or Path("config.yaml"))
        cfg = load_config(config_path)
    except FileNotFoundError as exc:
        err.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1) from exc
```

(c) Wrap the password resolution (replaces line 71, `passwords = resolve_passwords(cfg)`; the passphrase block and `snap_path` lines between (b) and (c) are untouched):

```python
    try:
        passwords = resolve_passwords(cfg)
    except RuntimeError as exc:
        err.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1) from exc
```

Keep the catches exactly this narrow — `FileNotFoundError` is what `load_config` raises for a missing config, `RuntimeError` is what `resolve_passwords` raises for missing keyring entries. Unexpected exceptions must still propagate (now as plain tracebacks without locals).

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: all tests PASS, coverage 100% (the two new except branches are exercised by the Step 1 tests; the happy paths by existing tests).

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py tests/test_cli.py
git commit -m "fix: curated errors for missing config/passwords; no rich tracebacks

export now prints load_config's and resolve_passwords' curated
one-liners and exits 1 instead of surfacing raw tracebacks. Typer
pretty exceptions are disabled because their locals rendering would
print resolved secrets to stderr on an unexpected crash —
redact_filter only covers logging output.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: CLAUDE.md gotcha + final verification

**Files:**
- Modify: `CLAUDE.md` (Gotchas section, and the `config.py` bullet under Architecture)

- [ ] **Step 1: Document the behaviour**

In `CLAUDE.md`:

(a) Append to the `config.py` bullet under **Architecture**:

```markdown
- `config.py` — pydantic models + YAML loader. Flat shape: `snapshot_path`, `terminal_path`, `accounts` at the top level. `snapshot_path` expands `~` at load time.
```

(b) Add a new bullet to **Gotchas** (after the "Investor passwords only" bullet):

```markdown
- **Typer pretty exceptions are disabled on purpose** (`pretty_exceptions_enable=False` in cli.py). Rich tracebacks render local variables, which after secret resolution would print the encryption passphrase and investor passwords to stderr — `redact_filter` only covers `logging` output. Don't re-enable them for prettier crashes. Expected errors (missing config, missing keyring entries) are caught in `export` and printed as curated one-liners.
```

- [ ] **Step 2: Run the full verification suite**

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: pytest green at 100% coverage; ruff, format, and mypy all clean.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record tilde expansion and pretty-exception gotcha in CLAUDE.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
