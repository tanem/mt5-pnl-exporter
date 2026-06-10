# Resilient prior-snapshot read in `export`

Date: 2026-06-11
Status: Approved (design)

## Background

`export` reads the existing snapshot before fetching, to (1) carry each
account's `currency`/`balance`/`equity`/`last_success_at` forward when that
account fails the current run (`cli.py:121-131`), and (2) decide whether to
keep the previous snapshot when *all* accounts fail — that decision keys off
`prior_by_login` being non-empty (`cli.py:135`).

The prior read (`cli.py:80-84`) only catches `FileNotFoundError`:

```python
try:
    prior = snapshot.read(snap_path, encryption_passphrase)
    prior_by_login = {a.login: a for a in prior.accounts}
except FileNotFoundError:
    pass
```

But `snapshot.read()` also raises `ValueError` when the file exists yet can't
be decoded — wrong passphrase, corrupt/truncated bytes, or an unsupported
schema version (`snapshot.py:167`, `:173`, `:178`). That exception is
uncaught, so `export` crashes before fetching anything. This bites in a real,
common case: the user changes the encryption passphrase (re-runs
`set-encryption-passphrase`), and every subsequent `export` dies trying to
decrypt the old file with the new passphrase, until they manually delete it.

The prior read is only an optimisation — a corrupt or stale prior should not be
fatal. It should behave like a missing file: warn and regenerate.

## Goals

- `export` tolerates an existing-but-unreadable prior snapshot: log a warning
  naming the file and why, then proceed with a fresh full export.
- An unreadable prior is treated as absent everywhere downstream — both the
  carry-forward (no prior account data) and the all-fail decision (no prior to
  keep, so the freshly-built snapshot is written).

## Non-goals

- No change to `snapshot.read()` — it stays strict; raising on an undecodable
  file is correct for the consumer contract. Resilience belongs at the
  `export` call site, which knows the prior is optional.
- No special-casing of the unsupported-schema-version `ValueError`. In a
  single-producer setup a prior the exporter wrote is always readable by it; a
  "newer schema" prior only arises on a version downgrade, which is unlikely
  enough that guarding it is overbuilding. All `ValueError`s from the prior
  read are treated uniformly.
- No retry, no backup-of-the-bad-file, no prompt. The snapshot is reproducible
  from the broker; regenerating is the right move.

## Design

### The change (`cli.py:80-84`)

Add a second `except` beside the existing `FileNotFoundError`:

```python
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

- Catch `ValueError` specifically, not bare `Exception`. That is exactly what
  `read()` raises for decrypt/corrupt/schema failures, and nothing else
  relevant.
- `RuntimeError` (empty passphrase) is unreachable here: `export` already
  exits early if the passphrase is unset (`cli.py:60-65`).
- `prior_by_login` stays `{}`, so the rest of `export` already does the right
  thing — failed accounts get empty/zero carry-forward values, and the all-fail
  branch (`error_count == len(accounts) and prior_by_login`) is false, so the
  freshly-built (all-error) snapshot is written rather than the bad file kept.

### Behavioural consequence

If the prior is unreadable *and* all accounts fail this run, the all-error
snapshot overwrites the unreadable file. This is intended: the unreadable file
holds nothing recoverable, and a readable error-snapshot (with `last_error`
populated) is strictly better than leaving an undecodable mystery file in
place. The self-heal on the next successful run then replaces it with real
data.

### Logging

`log.warning`, not `log.error`: the run still succeeds, so this is a warning,
not a failure. The original exception message is interpolated so the user can
tell a passphrase mismatch from a corrupt file. No secrets appear in the
message, and `redact_filter` scrubs logs regardless.

## Testing (TDD)

Two new CLI tests in `tests/test_cli.py`, using the existing fake-`DataSource`
harness (`install_fake`) and `_write_cfg`:

1. `test_export_regenerates_when_prior_unreadable` — plant garbage bytes at
   `snap_path` (`snap_path.write_bytes(b"not a valid age file")`), run `export`
   with a *succeeding* fake account. Assert: exit code 0; `snap_path` now
   decrypts with the configured `TEST_PASSPHRASE` and contains the account's
   real data; the "Could not read prior snapshot" warning is emitted.

2. `test_export_overwrites_unreadable_prior_when_all_fail` — same garbage prior
   plus a *failing* fake account. Assert: exit code 1; `snap_path` is now
   readable (the all-error snapshot replaced the garbage); the account's
   `last_error` is populated and `last_success_at` is `None`.

Writing garbage bytes is the simplest way to force the `ValueError` and
naturally exercises the corrupt-file path. The existing
`test_export_keeps_prior_snapshot_when_all_fail` (decodable prior is kept on
all-fail) stays unchanged and guards against regressing the happy path.

Coverage gate is 100%; both new `except`-branch lines must be exercised.

## Affected files / ripple

- `src/mt5_pnl_exporter/cli.py` — the new `except ValueError` branch.
- `tests/test_cli.py` — two new tests.
- `CLAUDE.md` — add a gotcha noting `export` tolerates an unreadable/corrupt
  prior snapshot (warns and regenerates), so a passphrase change no longer
  bricks it. No README change: the existing "idempotent, rebuilt each run"
  framing already covers the behaviour and contradicts nothing.
- No schema change; `schema/snapshot.schema.json` untouched.

## Verification

- `uv run pytest` — both new tests pass; 100% coverage holds (the two new
  branch lines covered).
- `uv run ruff check src/ tests/` and `uv run mypy src/mt5_pnl_exporter` clean.
- Manual narrative: with a snapshot on disk, change the keychain passphrase via
  `set-encryption-passphrase`, then run `export` — it now warns and writes a
  fresh snapshot instead of crashing.
