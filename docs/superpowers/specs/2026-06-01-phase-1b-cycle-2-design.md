# Phase 1b cycle 2: mandatory age encryption

Status: design. Approved 2026-06-01, ready to plan implementation.

Refines cycle 2 of [`2026-06-01-phase-1b-design.md`](2026-06-01-phase-1b-design.md)
(item 6) and folds in the gzip-before-encryption transport wrapper that
[`2026-06-01-phase-1b-cycle-1-design.md`](2026-06-01-phase-1b-cycle-1-design.md)
flagged as a forward-looking task.

## Why

The cycle 1 snapshot is plaintext JSON. Users who move it through a
third-party sync service (Dropbox, OneDrive, Syncthing) leave their full
trading history at rest on someone else's disk. Encrypting at rest closes
that gap. age is small, well-specified, and has multiple independent
implementations — a reasonable contract to commit to in 1.0.

Gzip lands in the same cycle because both belong at the transport layer
and both touch `snapshot.write` / `snapshot.read`. Compressing JSON-with-
repeated-field-names 5–10× makes the encrypted file viable on the same
sync services we're encrypting for.

## Wire format

The pipeline, applied left-to-right on write and right-to-left on read:

```
Snapshot model → JSON bytes → gzip → age (passphrase) → file
```

File extension by convention: `snapshot.json.gz.age`. The exporter writes
to `cfg.snapshot_path` verbatim — no auto-suffix, no enforcement.
`config.example.yaml` updates to the new extension so the convention is
documented. Consumers point at the same path the exporter writes; they
must implement the same pipeline in reverse to read it.

## Producer

`snapshot.write(path, snap, passphrase)` becomes the only write API.
Atomic-write semantics from cycle 1 are preserved — the temp file holds
the encrypted bytes.

```python
data = snap.model_dump_json(indent=2).encode()
compressed = gzip.compress(data)
encrypted = pyrage.passphrase.encrypt(compressed, passphrase)
tmp.write_bytes(encrypted)
tmp.replace(path)
```

`poll` retrieves the passphrase from the keychain before touching MT5; if
missing, it exits before any work happens (see below).

## Consumer

`snapshot.read(path, passphrase)` becomes the only read API.

```python
encrypted = path.read_bytes()
compressed = pyrage.passphrase.decrypt(encrypted, passphrase)
data = gzip.decompress(compressed)
raw = json.loads(data)
# existing schema-version check + Snapshot.model_validate
```

Decryption errors (`pyrage` exceptions) surface as `ValueError` with a
message naming the likely cause — wrong passphrase or corrupt file.
gzip errors after a successful decrypt are treated the same way (corrupt
or tampered payload).

Schema-version check and `Snapshot.model_validate` run on the decrypted
JSON exactly as today.

## Passphrase storage

Keychain under the existing `KEYRING_SERVICE = "mt5-pnl-exporter"`, with
account `"encryption-passphrase"`. No collision with login-keyed entries
(those use integer-string accounts).

`secrets.py` gains:

```python
ENCRYPTION_PASSPHRASE_ACCOUNT = "encryption-passphrase"

def get_encryption_passphrase() -> str | None: ...
def set_encryption_passphrase(passphrase: str) -> None: ...
```

Same `redact_filter` register pattern as investor passwords: on
retrieval, register with the filter so it's stripped from any log line.

## `set-encryption-passphrase` command

Mirrors `set-password`:

```bash
mt5-pnl-exporter set-encryption-passphrase
```

- No login argument — one passphrase per host.
- Prompts twice via `getpass` (entry + confirmation) and refuses on
  mismatch. Refuses empty input.
- On success, stores in keychain and prints a green confirmation to
  stderr.

## Missing-passphrase behaviour

Mandatory means: no passphrase, no work. `poll` checks the keychain
before any MT5 connection. On absence, exits 1 with this message to
stderr (literal text, used in tests):

```
Error: no encryption passphrase set in keychain.
Run 'mt5-pnl-exporter set-encryption-passphrase' first.
```

`snapshot.read()` raises `RuntimeError` with the same message body if
called with `passphrase=None`. Consumers that surface a friendlier
message can catch it.

No config flag, no `--no-encrypt` escape hatch, no two code paths. One
pipeline.

## Tests

- `test_snapshot.py` round-trip extended: write → read with passphrase,
  equality across all four record types.
- Wrong-passphrase read raises `ValueError` matching "wrong passphrase or
  corrupt file".
- Corrupt encrypted bytes (truncate the file) raise the same `ValueError`.
- Schema-version mismatch still detected after decrypt (existing test
  generalised — encrypt a v2-tagged blob, then tamper the inner JSON to
  v999, expect rejection).
- `snapshot.read(path, passphrase=None)` raises `RuntimeError` matching
  the documented missing-passphrase message.
- `test_secrets.py`: `set_encryption_passphrase` round-trips through the
  in-memory keyring fixture; `get_encryption_passphrase` returns `None`
  when unset.
- `test_cli.py`:
  - `poll` exits 1 with the documented stderr message when the
    encryption passphrase is missing — and does NOT touch the fake
    `MT5Source` (the in-test fake records calls; assertion: zero).
  - `poll` happy path: encryption passphrase fixtured into the in-memory
    keyring; verify the on-disk file decrypts cleanly with the same
    passphrase.
  - `set-encryption-passphrase`: empty refused; mismatched confirmation
    refused; success stores in keychain.
- The cycle 1 `tests/fixtures/sample_snapshot.json` stays as the plaintext
  reference. The encrypted file used in tests is generated in-test from
  the JSON fixture + a fixed test passphrase so it stays reproducible.

## Dependencies

Add to `[project.dependencies]`:

```
pyrage>=1.2
```

`gzip` is stdlib. No other new deps.

## Docs

CLAUDE.md:
- Add `set-encryption-passphrase` to the commands list.
- New gotcha: "Snapshot is mandatorily age-encrypted with a keychain-
  stored passphrase. `snapshot.read()` and `snapshot.write()` both
  require it; missing passphrase means `poll` refuses to run. Consumers
  must decrypt with the same passphrase."
- Update the architecture bullet for `snapshot.py` to mention the
  gzip + age pipeline.

README.md:
- Add `set-encryption-passphrase` to the quick-start, before `poll`.
- Update the `## Schema` section to note the file is age-encrypted JSON
  (gzipped before encryption).
- Update the snapshot-size note: gzip brings the 350 MB worst case down
  to ~35 MB on disk.

Full threat-model section is **cycle 3**, not here.

## Out of scope (deferred)

- **Recipient-key (X25519) mode.** Passphrase covers single-user. Add in
  1.x if a real recipient-mode scenario shows up.
- **Per-host passphrase rotation tooling.** Manual: run
  `set-encryption-passphrase` again on each host. No formal rotation
  workflow.
- **Compression-level knob.** `gzip.compress(data, compresslevel=9)`
  hardcoded — lower levels not exposed. The CPU cost is negligible
  versus the MT5 round-trip and writers care more about output size than
  encode speed.
- **Decryption error taxonomy.** One `ValueError` for any decrypt failure
  ("wrong passphrase or corrupt file"). Future could distinguish
  authentication failure from format error, but the user response is
  the same either way.
- **Encryption-format upgrade path.** If we ever change algorithms
  (recipient mode, different compressor), a new file extension is the
  signal. No in-band version byte.
