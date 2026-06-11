# Security audit — keychain reads, writes, and redaction boundaries

**Date:** 2026-06-01
**Branch:** `phase-1b-cycle-3`
**Audited commit:** `5398d81`

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
| `cli.py::export` (encryption passphrase load) | passphrase | keychain read → `snapshot.read/write` | ✓ | ✓ (registered with `redact_filter` on read) | ✓ goes only to `pyrage.passphrase.encrypt/decrypt` |
| `secrets.py::redact_filter` | n/a (boundary) | log filter | n/a | n/a | covers `logging` handlers only; `rich.Console` output bypasses it — see **Finding 2** |
| `config.py::check_file_perms` | n/a (boundary) | warn on `config.yaml` group/other-read | n/a | n/a | POSIX-only; no-op on Windows |

## Findings

### Finding 1 — `secrets.py` accepted empty secrets from callers

`set_investor_password("")` and `set_encryption_passphrase("")` would
have stored an empty value in the keychain. The CLI rejected empty
input before calling these setters, but the library did not — a
defence-in-depth gap reachable via programmatic misuse.

**Fix.** Both setters now raise `ValueError` on empty input. Patch
landed in commit `5398d81` (`src/mt5_pnl_exporter/secrets.py`).

### Finding 2 — `redact_filter` covers `logging` output only

`rich.Console` (`err.print` in `cli.py`) bypasses the filter. No
current `err.print` site interpolates a registered secret, so there is
no live leak. The risk is a future contributor adding an `err.print`
site without realising the filter would not catch it.

**Fix.** New `redact_filter.scrub(s: str) -> str` helper returns the
input with each registered secret replaced by `***`. Existing
`err.print` sites are audited and certified as clean; the helper is
available for any future site that needs to print a string possibly
containing a secret. Patch landed in commit `5398d81`
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
