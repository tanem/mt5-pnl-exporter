# Tilde expansion for `snapshot_path` + curated config/secret error UX

Date: 2026-06-12
Status: Approved (design)

## Background

A code review surfaced two bugs in how `export` handles configuration:

**Bug 1 — `~` in `snapshot_path` is never expanded.** `cli.py:68` builds the
target path with `Path(cfg.snapshot_path)` and no `expanduser()`. `pathlib`
does not expand `~` itself, so `snap_path.parent.mkdir(parents=True)` creates
a literal directory named `~` under the current working directory and writes
the snapshot there. Both `config.example.yaml:1` and `README.md:154` recommend
`snapshot_path: ~/snapshots/mt5.json.gz.age`, so anyone following the docs
hits this.

**Bug 2 — a missing config file shows a raw traceback, not the curated
message.** `export` calls `check_file_perms()` (`cli.py:56`) *before*
`load_config()`, and `check_file_perms` calls `path.stat()` (`config.py:54`).
When the config is absent, that `stat()` raises a bare `FileNotFoundError`
first, so the friendly "Copy config.example.yaml to config.yaml…" message in
`load_config` (`config.py:67`) is unreachable from the CLI. The
`RuntimeError` from `resolve_passwords` (missing keyring password,
`config.py:88`) likewise surfaces as a traceback. Worse, Typer's default
pretty exceptions render rich tracebacks **with local variables** — after
secret resolution, an unexpected crash in `export` would print
`encryption_passphrase` and the `passwords` dict to stderr, bypassing
`redact_filter` (which only covers `logging`). That is a secrets-disclosure
vector squarely within SECURITY.md's scope.

## Goals

- `~`-prefixed `snapshot_path` values resolve to the user's home directory on
  every platform, for every consumer of `Config.snapshot_path`.
- `export` with a missing config file, or with missing keyring passwords,
  prints the existing curated one-liner to stderr and exits 1 — no traceback.
- An unexpected crash never prints local variables (no secrets in crash
  output).

## Non-goals

- No expansion for `terminal_path` — it is a Windows `C:\…` executable path
  where `~` is not idiomatic; expanding it is speculative.
- No environment-variable expansion (`$VAR` / `%VAR%`) in any path — YAGNI.
- No change to per-account fetch error handling in the export loop — the
  existing broad `except Exception` with carry-forward behaviour stays.
- No change to `load_config`/`resolve_passwords` messages themselves — they
  are already right; the fix is making them reach the user.

## Design

### Bug 1: expansion in the `Config` model (`config.py`)

A `field_validator` on `snapshot_path` so the expansion happens once at load
time and every consumer sees the resolved value:

```python
@field_validator("snapshot_path")
@classmethod
def _snapshot_path_expand_user(cls, v: str) -> str:
    return str(Path(v).expanduser())
```

`Path.expanduser()` handles `~` via `USERPROFILE` on Windows and `HOME` on
POSIX; absolute paths pass through unchanged. `config.example.yaml` needs no
change — it becomes correct.

### Bug 2: curated errors reach the user (`config.py`, `cli.py`)

1. **`check_file_perms` early-returns when the file is absent:**

   ```python
   if not path.exists():
       return  # load_config will raise the curated FileNotFoundError
   ```

2. **`export` wraps its setup phase** — `check_file_perms`, `load_config`,
   and `resolve_passwords` — in one targeted handler:

   ```python
   try:
       check_file_perms(config_path or Path("config.yaml"))
       cfg = load_config(config_path)
       ...
       passwords = resolve_passwords(cfg)
   except (FileNotFoundError, RuntimeError) as exc:
       err.print(f"[red]Error: {exc}[/red]")
       raise SystemExit(1) from exc
   ```

   `FileNotFoundError` is what `load_config` raises for a missing config;
   `RuntimeError` is what `resolve_passwords` raises for missing keyring
   passwords. Nothing broader — unexpected exceptions still propagate.
   Restructuring note: the passphrase check and `redact_filter.register`
   between those calls stay where they are; only the ordering-sensitive setup
   moves inside the `try`. The existing encryption-passphrase-missing early
   exit (`cli.py:60-65`) is already curated and stays unchanged.

3. **Disable Typer pretty exceptions:**

   ```python
   app = typer.Typer(..., pretty_exceptions_enable=False)
   ```

   Unexpected crashes then print a plain Python traceback — no rich
   locals rendering, so no secret values in crash output. This is a
   deliberate security measure, recorded as a CLAUDE.md gotcha so a future
   contributor does not re-enable it for prettier output.

## Testing (TDD)

`tests/test_config.py`:

1. `test_snapshot_path_tilde_expands_to_home` — config with
   `snapshot_path: ~/snaps/mt5.json.gz.age`, monkeypatched `HOME` (and
   `USERPROFILE` for Windows runners if needed); assert
   `cfg.snapshot_path` starts with the fake home and contains no `~`.
2. `test_snapshot_path_absolute_unchanged` — an absolute path round-trips
   exactly.
3. `test_check_file_perms_missing_file_is_noop` — no exception, no output.

`tests/test_cli.py`:

4. Tighten `test_export_config_not_found` — assert exit 1, output contains
   "Copy config.example.yaml", and does **not** contain "Traceback".
5. `test_export_missing_investor_password_curated_error` — config OK,
   encryption passphrase set, keyring returns no investor password; assert
   exit 1 and the "set-investor-password" hint in output, no traceback.

Coverage gate is 100% with branch coverage; the new validator, early return,
and except-branch must all be exercised (the tests above cover each).

## Affected files / ripple

- `src/mt5_pnl_exporter/config.py` — validator + early return.
- `src/mt5_pnl_exporter/cli.py` — `pretty_exceptions_enable=False`, setup
  `try/except`.
- `tests/test_config.py`, `tests/test_cli.py` — tests above.
- `CLAUDE.md` — gotcha: pretty exceptions are disabled deliberately (locals in
  rich tracebacks would leak secrets); `snapshot_path` supports `~`.
- No model/schema change; `schema/snapshot.schema.json` untouched (Config is
  not part of the snapshot schema).
- README: no change required — `~` in the example now simply works.

## Verification

- `uv run pytest` — new tests pass, 100% coverage holds.
- `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`,
  `uv run mypy src/mt5_pnl_exporter` clean.
- Manual narrative: `mt5-pnl-exporter export` with no `config.yaml` prints the
  one-line "Copy config.example.yaml…" error and exits 1 with no traceback;
  with `snapshot_path: ~/snaps/…` the file lands under the real home
  directory, and no `~` directory appears in the CWD.
