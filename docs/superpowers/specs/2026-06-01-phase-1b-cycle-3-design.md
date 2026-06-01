# Phase 1b cycle 3: docs reframe, threat model, and keychain audit

Status: design. Approved 2026-06-01, ready to plan implementation.

Refines cycle 3 of [`2026-06-01-phase-1b-design.md`](2026-06-01-phase-1b-design.md)
(items 7 and 8). Picks up the threat model that
[`2026-06-01-phase-1b-cycle-2-design.md`](2026-06-01-phase-1b-cycle-2-design.md)
explicitly deferred. Mostly docs and an evidence-style audit, with two
small audit-driven code patches.

## Why

Cycles 1 and 2 changed both the snapshot shape and the on-disk format
(gzip + age). The user-facing docs still frame the exporter around a
"Windows VPS" deployment and never spell out what the encryption is
actually protecting. Cycle 3 closes that gap: reframes the host story
around the Windows machine where MT5 runs, lands a written threat model
so users can judge the contract, and produces a point-in-time audit of
every keychain read/write site as evidence that the implementation
matches what the docs claim.

## Deliverables

Four deliverables, sequenced so the audit can reference the code patches.

1. **Threat model section** in `README.md` (new `## Threat model`).
2. **Windows-host reframe** across `README.md` and `CLAUDE.md`.
3. **Keychain/perms audit** at `docs/security-audit.md` (new file).
4. **Two audit-driven code patches** in `src/mt5_pnl_exporter/secrets.py`
   (+ tests).

## Threat model section

New `## Threat model` section in `README.md`. Around 300–400 words. NZ
English, no hyperbole. No code blocks, no operational recipes (Syncthing
setup etc. — explicitly out of scope per the parent spec).

Structure:

**Trust boundary.** One paragraph. "The OS user account on the Windows
host that runs the exporter is the trust boundary. Anyone with that
account's session can read the keychain, run `poll`, and read decrypted
snapshots. The same applies to a consumer machine: anyone with that
account's session can decrypt the snapshot. The exporter does not defend
against a compromised user session on either side."

**What's protected.** Bulleted list:

- Snapshot contents at rest *off* the Windows host — sync services
  (Dropbox, OneDrive, Syncthing), backups, transit. Mandatory age
  encryption is what gets you this.
- Investor passwords and the encryption passphrase, on disk and in logs.
  Stored only in the OS keychain; `redact_filter` strips registered
  secrets from log lines.

**What's not protected.** Bulleted list:

- A compromised user session on either host. With keychain access the
  snapshot decrypts to plaintext.
- Traffic-analysis metadata — file size, sync timing, whether a poll
  ran today. age hides contents, not existence.
- Passphrase loss. There is no recovery. Mitigation: the snapshot is
  reproducible — re-run `poll` to rebuild it from broker history.
- The broker side. MT5 deal history lives on the broker's server and is
  governed by their controls, not by anything in this tool.

**Transport guidance.** Short paragraph. Once the file is encrypted at
rest, transport choice carries less weight than it used to: scp/rsync
over SSH, a synced folder (Dropbox/Syncthing/OneDrive), or reading on
the same machine are all viable. Pick whichever fits the workflow.

## Windows-host reframe

The current docs treat "VPS" as the assumed deployment. The exporter
runs on the Windows machine where MT5 is installed — a VPS is one
choice among several, not the assumption.

**`README.md` edits:**

- First line: "Polls MT5 deal history on a Windows VPS" → "Polls MT5
  deal history on the Windows host where MT5 runs".
- `## Install` block: comment `# VPS, includes MetaTrader5` →
  `# Windows host with MT5`.
- `## Quick start (VPS)` heading: drop the `(VPS)` qualifier. Commands
  themselves do not change.

**`CLAUDE.md` edits:**

- First paragraph: "polls MT5 deal history on a Windows VPS" →
  "polls MT5 deal history on the Windows host where MT5 runs".
- Commands block comment: `# VPS: also install MetaTrader5` →
  `# Windows host: also install MetaTrader5`.
- Gotcha: "stored in the VPS keychain via `keyring`" → "stored in the
  OS keychain via `keyring` on the Windows host".

What stays unchanged: the architecture/gotchas about `MetaTrader5`
being Windows-only, the dedicated-terminal requirement,
`check_file_perms` being POSIX-only, and the schema command being
cross-OS — all correct as-is.

What is *not* added: no "supported platforms" matrix, no `## Requirements`
section, no Wine/macOS notes. The existing "Windows-only because MT5 is
Windows-only" framing is implicit in "the Windows host where MT5 runs"
and that is enough for a single-user tool.

## Keychain / perms audit

New file `docs/security-audit.md`. Point-in-time evidence, dated
`2026-06-01`. Future audits supersede.

**Preamble (~100 words).** "Audit of every keychain read/write and every
site where a keychain-sourced secret crosses a trust boundary in
`mt5-pnl-exporter` at commit `<HEAD>`. Each row checks three properties:
the secret is never written to disk outside the keychain, never appears
in log output, and never crosses the `redact_filter` boundary
unredacted. Findings are listed below the table with patch references."

**Table columns.**

| Site (file:lineish) | Secret | Direction | Never on disk | Never in logs | Past redact boundary |

**Rows — six secret-touching sites:**

1. `secrets.py::get_investor_password` — investor pw — keychain read —
   n/a — n/a — ✓ returns to caller.
2. `secrets.py::set_investor_password` — investor pw — keychain write —
   ✓ — ✓ — ✓ accepts from caller.
3. `secrets.py::get_encryption_passphrase` — passphrase — keychain read
   — same shape as row 1.
4. `secrets.py::set_encryption_passphrase` — passphrase — keychain write
   — same shape as row 2.
5. `config.py::resolve_passwords` — investor pw — keychain read,
   returned as dict — ✓ — ✓ (registered with `redact_filter` immediately
   on read) — ✓ scoped to `MT5Source._passwords`.
6. `cli.py::poll` (encryption passphrase load) — passphrase — keychain
   read, threaded to `snapshot.read/write` — ✓ — ✓ (registered with
   `redact_filter` immediately on read) — ✓ goes only to
   `pyrage.passphrase.encrypt/decrypt`.

**Plus two supporting rows** that don't touch a secret directly but
matter to the boundary story:

7. `secrets.py::redact_filter` — covers `logging` handlers only;
   `rich.Console` output bypasses it. No current `err.print` site
   interpolates a registered secret — see **Finding 2**.
8. `config.py::check_file_perms` — checks `config.yaml` mode bits on
   POSIX, warns on group/other-readable. No-op on Windows. Doesn't
   touch secrets but is the only file-permission defence in the
   codebase; included so a reader sees the full picture.

**Findings.**

- **Finding 1 — `secrets.py` accepts empty secrets from callers.**
  `set_investor_password("")` and `set_encryption_passphrase("")` would
  store an empty value in the keychain. The CLI guards against this,
  but the library does not. Risk: low (only reachable via programmatic
  misuse), but defence-in-depth is cheap. **Fix:** raise `ValueError`
  from both setters on empty input. Patch lands in this PR.
- **Finding 2 — `redact_filter` only covers `logging` output.**
  `rich.Console` (`err.print`) bypasses the filter. No current
  `err.print` site interpolates a registered secret, so there is no
  live leak. Risk: future-contributor footgun. **Fix:** add
  `redact_filter.scrub(s: str) -> str` so any future site that needs
  to print a string possibly containing a secret has a one-call
  helper. The audit certifies current call sites as clean. Patch
  lands in this PR.

**Closing.** One line: "Re-run this audit when adding any new keychain
access, log output, or `Console` site." Then a short `## Method`
sub-section (two lines) describing the grep used and the criteria, so
future audits are reproducible.

## Code patches

Both patches live in `src/mt5_pnl_exporter/secrets.py`.

### Empty-string guards

```python
def set_investor_password(login: int, password: str) -> None:
    if not password:
        raise ValueError("password cannot be empty")
    keyring.set_password(KEYRING_SERVICE, str(login), password)


def set_encryption_passphrase(passphrase: str) -> None:
    if not passphrase:
        raise ValueError("passphrase cannot be empty")
    keyring.set_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT, passphrase)
```

The CLI already rejects empty input *before* calling these setters and
keeps its user-facing Rich-coloured error messages. Library-level
guard is defence in depth — protects against programmatic misuse and
against any future caller that forgets the check.

### `redact_filter.scrub` helper

```python
class _RedactFilter(logging.Filter):
    # ...existing __init__, register, filter unchanged...

    def scrub(self, s: str) -> str:
        """Return `s` with each registered secret replaced by ***."""
        if not self._secrets:
            return s
        pattern = "|".join(self._secrets)
        return re.sub(pattern, "***", s)
```

Documents the available pattern. Not retrofitted onto existing
`err.print` sites — the audit certifies they don't interpolate a
secret today. Future contributors can wire through `redact_filter.scrub`
if they ever need to.

## Tests

`tests/test_secrets.py` gains:

- `set_investor_password("")` raises `ValueError` matching
  "password cannot be empty".
- `set_encryption_passphrase("")` raises `ValueError` matching
  "passphrase cannot be empty".
- `redact_filter.scrub("hello pw123 world")` returns `"hello *** world"`
  after registering `"pw123"`.
- `redact_filter.scrub` returns input unchanged when no secrets are
  registered.
- `redact_filter.scrub` handles multiple registered secrets in one
  string.

`tests/test_cli.py`: no new tests. The existing "empty password
refused" CLI tests still pass — the CLI guard catches empty input
before reaching `secrets.py`, so behaviour at the CLI boundary is
unchanged.

Coverage target stays ≥95%.

## Branching and PR

Branch `phase-1b-cycle-3` from `main` (currently `bf64ba0`). No direct
pushes to `main`. Plan ends with: commit straggling changes → push
branch → open draft PR. PR description names the three docs deliverables
and the two audit findings.

## Out of scope (deferred)

- **Retrofitting `redact_filter.scrub` onto existing `err.print` sites.**
  None currently interpolate a registered secret; the audit certifies
  them. Adding the helper is enough for new sites.
- **`KEYRING_SERVICE` rename / migration tooling.** Settled in phase 1a.
- **Recipient-key (X25519) encryption mode, signing, traffic-layer
  hardening.** Out of scope per the parent spec.
- **Version policy, tag, PyPI publish.** Cycle 4.
- **Editing prior specs.** Each prior spec's "deferred to cycle 3"
  clause matches what is actually landing here; no design-doc-hygiene
  edits required.
