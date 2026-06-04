# Security policy

## Scope

This tool handles **read-only MT5 investor passwords** — credentials that can view account data but cannot place or modify trades — and a **snapshot encryption passphrase** used to age-encrypt the on-disk snapshot. Both live only on the Windows host where `poll` runs, in its OS keychain via `keyring` (Windows Credential Manager). Neither is written to disk, logs, or the snapshot file.

Vulnerabilities in scope:

- Secrets disclosure (investor passwords, the encryption passphrase, account numbers, or balances leaking in logs, the snapshot, or any other output)
- Unsafe keychain read/write behaviour
- Snapshot encryption pipeline (gzip + `age`) bypassed, weakened, or producing files readable without the passphrase
- Snapshot written in a way that allows partial reads or unauthorised access by other local users
- Dependency vulnerabilities with a plausible exploitation path in this tool

Out of scope:

- MT5 server or broker infrastructure (not under this project's control)
- Issues only reproducible with a non-current Python or uv version

## Reporting

**Do not open a public GitHub issue for security vulnerabilities.** Public issues expose the vulnerability before a fix is available.

Report privately via the Security tab — [Report a vulnerability](https://github.com/tanem/mt5-pnl-exporter/security/advisories/new). This opens a private workspace visible only to you and the maintainer.

You will receive a response within 7 days. Once a fix is ready, I'll agree a disclosure date with you before publishing.
