# Snapshot verification docs

Date: 2026-06-10
Status: Approved (design)

## Background

The docs describe the on-disk encryption pipeline but never give a runnable
command to read a snapshot back. `README.md` says readers must reverse the
pipeline (`age decrypt → gunzip → json.loads`) and shows what the decrypted
JSON looks like, but offers no actual command. `CONTRIBUTING.md`'s
"Smoke-test a real export" section stops at step 5 — *"confirm it logs `OK`
per account and writes the snapshot"* — verifying that the export *ran*, never
that the artifact *decrypts to sane contents*.

So the moment a contributor or consumer wants to eyeball the file, they are on
their own. The obvious instinct — double-clicking the `.age` file in Windows
Explorer — dead-ends with "Windows can't open this type of file (.age)",
because the file is ciphertext. This change closes that gap with a
copy-pasteable decode command for each audience.

## Goals

- Give a contributor a verification step that reads a freshly-exported
  snapshot back through the project's own read path, confirming the artifact
  round-trips — not just that `export` ran.
- Give a consumer (building a reader in any language) a runnable, language-
  agnostic decode command next to the existing pipeline description.
- Name the "you can't open the file directly — it's ciphertext" dead-end in one
  line, so the reader doesn't repeat the Explorer mistake.

## Non-goals

- No full `model_dump(indent=2)` dump in the docs — useful ad hoc, but noise in
  a reference.
- No dedicated Troubleshooting section keyed on the "Windows can't open .age"
  symptom — a one-line caveat covers it without the weight.
- No code, schema, or behaviour change. Docs only.
- No `CLAUDE.md` change — this is not a command/architecture/gotcha change, so
  the doc-sync rule does not trigger.

## Design decisions

- **Both audiences.** Contributors (verifying a real export) and consumers
  (building a reader) each get a decode path.
- **Tailored commands per audience.** CONTRIBUTING uses the Python
  `snapshot.read()` one-liner because a contributor has the package installed
  and this exercises the project's *actual* validated read path — the real
  consumer contract (reverses the pipeline *and* validates the full pydantic
  model). README uses the language-agnostic `age` CLI so a consumer in any
  language sees how to decode without coupling to internal modules.
- **One-line ciphertext caveat**, not a troubleshooting subsection.
- **`age -d` takes no `-p` on decrypt.** `--passphrase` is an encrypt-only
  flag; on decrypt, age auto-detects a passphrase-encrypted (scrypt) file and
  prompts. The correct consumer command is `age -d mt5.json.gz.age | gunzip`.
  The exporter encrypts via `pyrage`, but the output is standard age format, so
  the `age` CLI decrypts it.

## Changes

### A. CONTRIBUTING.md — add step 6 to "Smoke-test a real export"

Append a verification step after the current step 5. Reads the snapshot back
through `snapshot.read()`, which reverses the pipeline and validates the model:

> 6. Verify the snapshot decrypts and validates — this exercises the same
>    `age → gzip → JSON` read path a consumer uses. The on-disk file is
>    ciphertext, so opening it directly won't work; read it back via the API:
>
>    ```bash
>    uv run python -c "from pathlib import Path; import mt5_pnl_exporter.snapshot as s, mt5_pnl_exporter.secrets as sec; snap = s.read(Path('<snapshot_path>'), sec.get_encryption_passphrase()); print(snap.generated_at, '|', len(snap.closed_deals), 'deals,', len(snap.open_positions), 'open,', len(snap.cash_flows), 'cash flows'); [print(a.login, a.label, a.balance, a.equity) for a in snap.accounts]"
>    ```
>
>    Replace `<snapshot_path>` with your configured `snapshot_path`. If it
>    prints without raising, the file is structurally sound — `read()` reverses
>    the pipeline and validates the full pydantic model.

### B. README.md — decode snippet near the pipeline description

Add a short snippet next to the existing "readers must reverse the pipeline"
text (around the Snapshot-format / decode description). Language-agnostic, with
the one-line ciphertext caveat up front:

> The on-disk file is ciphertext — you can't open it directly (double-clicking
> a `.age` file just fails). Reverse the pipeline to read it. With the
> [age](https://age-encryption.org/) CLI installed (`brew install age` on
> macOS; see the age site for other platforms):
>
> ```bash
> age -d mt5.json.gz.age | gunzip     # prompts for the passphrase, prints the JSON
> ```

Install guidance is deliberately one example plus the upstream link, not a
per-OS matrix — the producer host is Windows, consumers run anywhere, and a
full matrix would duplicate upstream and go stale (consistent with the repo's
no-restating-upstream stance). The `age` homepage carries the full matrix.

## Affected files / ripple

- `CONTRIBUTING.md` — new step 6 in "Smoke-test a real export".
- `README.md` — decode snippet + one-line ciphertext caveat near the existing
  pipeline description.
- `CLAUDE.md` — no edit; confirm the new wording doesn't contradict the
  existing encryption gotchas.

## Verification

- Run the CONTRIBUTING step-6 one-liner against a real snapshot on the Windows
  host (live-testable during the current smoke test): it prints the account
  summary without raising.
- Run `age -d mt5.json.gz.age | gunzip` on a host with the `age` CLI installed
  (e.g. macOS via `brew install age`): it prompts for the passphrase and prints
  the JSON.
- No tests, schema, or code touched — `uv run pytest` unaffected (docs-only).
