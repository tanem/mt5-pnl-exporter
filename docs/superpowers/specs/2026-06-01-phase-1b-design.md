# Phase 1b: exporter simplifications and 1.0

Status: design. Approved 2026-06-01, ready to plan implementation.

Builds on [`2026-05-31-repo-split-design.md`](2026-05-31-repo-split-design.md).
That spec's Phase 1b bullets are the contract this brainstorm constrains.

## Why

Phase 1a ported the exporter as-is. Before tagging `1.0` and committing
publicly to a schema, two threads need to land:

- **Don't predict the future.** The ported snapshot pre-aggregates closing
  deals into `DailyRow`, baking in a day-grouping assumption and discarding
  most of what MT5 emitted (symbol, direction, volume, time-of-day, individual
  deal components, magic, open positions, deposits/withdrawals). The exporter
  has no way to know what a consumer will want to slice by. The principle:
  grab every relevant field, let consumers slice.
- **Transport is undefined.** The repo-split spec said `snapshot.json` is the
  contract but was silent on how it gets from the Windows host to a reader on
  another machine. For users moving the snapshot through a sync service
  (Dropbox, OneDrive, Syncthing), the file at rest sits on third-party
  servers in plaintext. Mandatory encryption closes that gap.

Tagging `1.0` is also a chance to drop or rename a few things that no longer
fit now that the query side has left for the Go CLI repo.

## Scope

Nine items, grouped into four cycles (see *Cycle decomposition* below):

1. Snapshot redesign — raw closed deals (full per-deal fields), open
   positions, cash flows.
2. MT5 source extensions — fetch the new fields, fetch open positions, retain
   balance deals as cash flows.
3. Drop `FixtureSource` as a runtime source; move smoke fixtures to `tests/`.
4. Tests restructured around snapshot + sources (was: aggregate-focused).
5. Config flatten — drop the `poll:` role-scoping wrapper now that there is
   no `query:` side.
6. Mandatory age encryption of `snapshot.json.age` with a passphrase,
   keychain-stored.
7. Docs reframe — replace VPS framing with "Windows host with MT5"; add a
   *Threat model* section to README.
8. Keychain / perms audit — correctness pass against the new framing.
9. Major.minor version policy (`SCHEMA_VERSION = "1.0"`), git tag `1.0`,
   PyPI publish held for final review.

## Snapshot redesign

The new snapshot keeps raw data only. Aggregation moves to consumers.

```
Snapshot
├── schema_version: "1.0"
├── generated_at: ISO-8601 UTC string
├── accounts: list[AccountSnapshot]
├── closed_deals: list[ClosedDeal]
├── open_positions: list[OpenPosition]
└── cash_flows: list[CashFlow]
```

`AccountSnapshot` keeps login, label, currency, balance, equity,
`last_success`, `last_error`. No win/loss/profit-factor — that is all
derivable from `closed_deals`.

`ClosedDeal` carries the full MT5 deal record for each closing deal: ticket,
account, symbol, type (long/short), entry, volume, open/close prices,
open/close times (Unix), profit/swap/commission/fee, magic. The exact field
list is settled in cycle 1's own brainstorm.

`OpenPosition` carries each currently-open position for floating P&L (login,
ticket, symbol, type, volume, open price, open time, current price, profit).
Settled in cycle 1.

`CashFlow` carries each balance deal — deposits, withdrawals, credits — that
the current exporter filters out: login, time, amount, type, comment. Field
list settled in cycle 1.

`aggregate.py` is deleted. `deals_to_daily()` has no caller in the new model.

## Mandatory age encryption

The exporter writes `snapshot.json.age` — an age-encrypted blob containing
the JSON snapshot. [age](https://age-encryption.org) is a small, modern,
well-spec'd file-encryption format with multiple independent implementations
(Go canonical, Rust, JS).

**Passphrase mode.** A single shared passphrase encrypts on the producer
side and decrypts on the consumer side. Mirrors the existing investor-password
pattern: stored in the OS keychain on each machine, never on disk, never in
logs.

**Producer flow.** Exporter builds `Snapshot` → serialises to JSON in memory
→ reads passphrase from keychain → age-encrypts (scrypt-derived key) →
atomically writes `snapshot.json.age` (temp file + replace).

**Consumer flow.** Reader opens `snapshot.json.age` → reads passphrase from
local keychain → decrypts in memory → existing schema-version check +
`Snapshot.model_validate` against the decrypted JSON.

**Mandatory, not opt-in.** No config flag, no two code paths. Without a
configured passphrase, `poll` exits with a clear error:

```
Error: no encryption passphrase set in keychain.
Run 'mt5-pnl-exporter set-encryption-passphrase' first.
```

This refuses to write rather than silently producing plaintext.

**New command.** `mt5-pnl-exporter set-encryption-passphrase` — prompts,
stores in keychain. Mirrors `set-password`.

**Consumer contract.** All consumers MUST support age decryption against a
shared passphrase to be usable. The schema-version check runs against
decrypted bytes.

Detailed UX (config knob shape, keychain key name, error-message exact text,
which age library is wired in) is settled in cycle 2's brainstorm.

## Other simplifications

**Config flatten.** With the `query:` section gone, the `poll:` role-scoping
wrapper has no peer. Flatten `poll.terminal_path` to `terminal_path` at the
top level. The result:

```yaml
snapshot_path: ...
terminal_path: ...
accounts:
  - login: ...
    label: ...
```

**Drop `FixtureSource` as a runtime source.** The `--source fixture` flag
and the `FixtureSource` implementation go away. Smoke-test fixtures move to
`tests/fixtures/` and are loaded directly by tests rather than via a runtime
source-selection knob. The `DataSource` protocol stays — `MT5Source` is the
only implementation.

**Tests restructured.** Tests pivot from `aggregate.py` (gone) to the
snapshot round-trip and source contracts. Coverage target stays at 95%.

## Docs + threat model

**Reframe.** Replace VPS framing across README.md and CLAUDE.md with
"Windows host with MT5". The exporter runs on any Windows machine with MT5
installed — VPS is one deployment choice among several, not the assumption.

**Threat model section** in the README, covering explicitly:

- Trust boundary: the OS user account on the Windows host. Anyone logged in
  as you on that host can read the keychain, run the exporter, and read
  decrypted snapshots.
- What's protected: snapshot contents at rest off the Windows host (sync
  services, backups, transport). Investor passwords on disk and in logs.
- What's not protected: a compromised user session on either machine.
  Traffic-analysis metadata. Passphrase loss (snapshot is recoverable by
  re-polling MT5; the deal history is broker-side).
- Transport guidance: scp/rsync over SSH, synced folder (now safe by default
  thanks to encryption), or same-machine reading. The encrypted-at-rest
  property makes the choice of transport less load-bearing than it used
  to be.

**Keychain / perms audit.** Quick correctness pass on `secrets.py` and
`check_file_perms` in `config.py` against the new framing. Likely no code
changes — confirm the implementation matches what we document.

## Version policy and release

**Major.minor.** `SCHEMA_VERSION` moves from `int = 1` to `str = "1.0"`.
`read()` parses the stamp as major.minor and accepts a configured range
(default: exact major match). Minor bumps add optional fields; major bumps
are breaking.

**Tag order.** Git tag `1.0` lands first — once cycles 1–3 are merged and a
final review pass has been done locally. PyPI publish is a separately-gated
step in cycle 4: tag, review, then publish (or hold).

**PyPI.** Publishes as `mt5-pnl-exporter` with the `[mt5]` optional dep
group. README documents `uv tool install "mt5-pnl-exporter[mt5]"`. Trusted
publishing via GitHub Actions OIDC.

## Cycle decomposition

Four cycles, each with its own brainstorm → spec → plan → execute.

**Cycle 1 — Snapshot redesign and cascades.** Items 1, 2, 3, 4, 5. The big
one. Settles the exact field list per record type. Drops `aggregate.py`,
drops `FixtureSource`, flattens config, pivots tests. Lands at
`SCHEMA_VERSION = 2` (still integer; the public commitment hasn't happened
yet).

**Cycle 2 — Mandatory age encryption.** Item 6. Adds the age dependency,
the `set-encryption-passphrase` command, encrypt-on-write in `poll`,
decrypt-on-read in `snapshot.read()`. Schema unchanged from cycle 1 —
encryption is a transport wrapper, not a schema change.

**Cycle 3 — Docs and security framing.** Items 7, 8. Runs after cycle 2 so
the docs reflect the final shape. README rewrite, CLAUDE.md update, threat
model section, keychain/perms audit. Likely a small audit-driven code patch.

**Cycle 4 — Version policy and release.** Item 9. `SCHEMA_VERSION` becomes
`"1.0"`; `read()` does range parsing. Git tag `1.0`. PyPI publish held as a
separately-gated step pending a final cross-cycle review.

Cycles run sequentially. Each lands stable on `main` before the next starts.

## Open design questions

Deferred to per-cycle brainstorms — listed here for visibility, not for
resolution now.

- Cycle 1: exact field lists for `ClosedDeal`, `OpenPosition`, `CashFlow`.
  How to handle MT5's open-position `time_update` vs `time` fields. Whether
  to keep deal `type` / `entry` as MT5 integers or translate to enums in the
  schema. How to handle currency across accounts (probably: don't convert —
  record each account's native currency, let consumers convert).
- Cycle 2: config knob shape for encryption; keychain entry name; exact
  error-message strings; whether to depend on `pyrage` (Rust-backed) or a
  pure-Python age implementation.
- Cycle 3: threat-model section length and tone; whether to add a small
  "operational recipes" section (scp cronjob, Syncthing setup) or leave
  transport entirely to the user.
- Cycle 4: supported-range default for `read()` (exact major, or accept any
  minor under same major); release-workflow shape.

## Out of scope (deliberately)

- **Recipient-key (X25519) encryption mode.** Passphrase mode covers every
  realistic scenario for a single-user tool. Recipient mode adds genuine
  key-management UX cost for no current use case. Add in 1.x if a real
  scenario justifies it.
- **Snapshot signing.** age's authenticated encryption already detects
  tampering on decrypt. Standalone signatures would be useful only if
  encryption were optional — which it isn't.
- **Encryption-at-rest beyond age.** No disk-level encryption configuration,
  no encrypted keychain wrappers, no in-memory mlock — the OS keychain and
  age together are the model.
- **UI architecture.** Phase 4's brainstorm picks. See *Forward
  compatibility* below.
- **Live API / HTTP layer.** Out of scope per the parent spec; still out of
  scope.

## Forward compatibility (Phase 4 UI)

The mandatory-encryption decision constrains the UI's read path but does
not constrain its architecture. All of the following are compatible with
the contract (file is age-encrypted, passphrase is shared, decryption in
the consumer):

- **Tauri shell.** Rust binary with a webview. `age` Rust crate handles
  decrypt. Reads passphrase from the OS keychain — same pattern as the CLI.
  No passphrase re-typing, no file-picker UX.
- **Electron shell.** Same idea in JS land. `age-encryption` npm package
  for decrypt. Heavier install than Tauri.
- **Pure browser.** Static SPA (e.g. on GitHub Pages, served `file://`, or
  self-hosted). `age-encryption.js` decrypts in the browser. Drag-and-drop
  or File System Access API for the file; passphrase prompted each session
  (or held in browser storage if the user opts in).

Phase 4 brainstorm picks based on appetite at that time. No code in this
phase pre-commits to one path.
