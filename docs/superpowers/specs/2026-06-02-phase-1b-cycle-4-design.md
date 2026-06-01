# Phase 1b cycle 4: version policy and the 1.0 release

Status: design. Approved 2026-06-02, ready to plan implementation.

Refines cycle 4 of [`2026-06-01-phase-1b-design.md`](2026-06-01-phase-1b-design.md)
(item 9). Closes phase 1b. Lands the `1.0` version stamp on the schema,
adds the range-parsing reader, and prepares `pyproject.toml` for the
first PyPI publish. The git tag and the publish itself are post-merge
manual steps — the cycle 4 PR is code only.

## Why

Cycles 1–3 settled the schema shape, the on-disk format, the docs, and
the security framing. The remaining gap before a 1.0 commitment is the
version stamp: today it's a bare integer (`SCHEMA_VERSION = 2`), which
gives the reader no way to express "I can read this older minor" or "I
can't read this newer major". Cycle 4 swaps the stamp for `major.minor`
strings and teaches `read()` to accept the same major up to its own
minor — the convention that lets future cycles add optional fields
without breaking older consumers.

The same PR bumps `pyproject.toml` to `1.0.0` and tightens the package
metadata enough to publish to PyPI cleanly. The tag and the publish
themselves sit outside the PR so each is a discrete, reviewable act.

## Deliverables

Five deliverables, all in one code-only PR.

1. `SCHEMA_VERSION` becomes the string `"1.0"`.
2. `snapshot.read()` parses the stamp as `major.minor` and accepts the
   same major up to its own minor; otherwise it raises a readable
   `ValueError`.
3. `Snapshot.schema_version` field becomes `Literal["1.0"]`; the schema
   file is regenerated.
4. `pyproject.toml` gains `version = "1.0.0"`, a neutral description,
   and a `readme = "README.md"` reference.
5. README and CLAUDE.md updates reflecting the new stamp format.

## Range-parsing semantics

The reader applies one rule: same major, minor less than or equal to
the code's minor. `read()` rejects anything else with a single error
message that names the supported range.

```python
SCHEMA_VERSION = "1.0"
_MAJOR = 1
_MINOR = 0


def _parse_version(stamp: object) -> tuple[int, int]:
    if not isinstance(stamp, str):
        raise ValueError(f"schema_version must be a string like '1.0', got {stamp!r}")
    parts = stamp.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"schema_version {stamp!r} is not in major.minor form")
    return int(parts[0]), int(parts[1])
```

Inside `read()`, replace the current integer equality check with:

```python
file_major, file_minor = _parse_version(raw.get("schema_version"))
if file_major != _MAJOR or file_minor > _MINOR:
    raise ValueError(
        f"Snapshot schema_version {raw.get('schema_version')!r} is not "
        f"supported by this reader (accepts {_MAJOR}.0–{_MAJOR}.{_MINOR}). "
        "Upgrade mt5-pnl-exporter, or re-run 'poll' on a compatible host."
    )
```

The model field tightens in lockstep: `Snapshot.schema_version:
Literal["1.0"]`. At 1.0 the range check and the literal happen to
overlap exactly; the separation lets a future 1.1 reader widen the
literal (`Literal["1.0", "1.1"]`) while the parser stays untouched.

**Why two layers of check?** The raw-dict pre-check produces an error
message a human can act on. Pydantic's literal-mismatch errors are
noisier and would surface before the friendlier diagnostic if the field
literal were the only gate. Keeping the bespoke pre-check above
`model_validate` keeps the diagnostic clean.

**No configuration surface.** No `accepted=` parameter, no env var, no
override. There is one version in existence; configurability is
something to add when there's a real caller asking for it.

## `pyproject.toml` changes

Minimal: enough to publish without embarrassing the project's PyPI
page, no further.

```toml
[project]
name = "mt5-pnl-exporter"
version = "1.0.0"
description = "MT5 P&L exporter — polls deal history on the Windows host where MT5 runs and writes a typed, encrypted snapshot."
readme = "README.md"
authors = [
    { name = "Tane Morgan", email = "464864+tanem@users.noreply.github.com" }
]
requires-python = ">=3.12"
# dependencies, optional-dependencies, scripts unchanged
```

Three edits: `version` bump, `description` drops "Windows VPS" framing,
new `readme = "README.md"` line so PyPI renders the README on the
project page. Everything else (`license =`, `[project.urls]`,
`classifiers = [...]`) lands in the follow-up PR alongside the GHA
publish workflow — see below.

## Tests

`tests/test_snapshot.py`:

**Fixture updates** (mechanical). Every `schema_version=2` literal
becomes `schema_version="1.0"`. The v999-rejection test plants `"2.0"`
instead (wrong major, same readable rejection).

**Reworked existing tests:**

- `test_read_rejects_wrong_schema_version_after_decrypt` — planted stamp
  becomes `"2.0"`; assertion matches `"not supported"`.
- `test_read_rejects_missing_schema_version_after_decrypt` — still
  exercises the `raw.get(..., None)` branch; the missing stamp now
  routes through `_parse_version`'s "must be a string" arm.

**New tests** (six):

- `test_parse_version_accepts_major_minor` — `("1.0") == (1, 0)`,
  `("2.7") == (2, 7)`.
- `test_parse_version_rejects_non_string` — `_parse_version(2)` raises
  matching `"must be a string"`.
- `test_parse_version_rejects_wrong_shape` — `"1"`, `"1.0.0"`, `"1.a"`,
  `""` each raise matching `"major.minor"`.
- `test_read_accepts_exact_current_version` — round-trip with `"1.0"`
  succeeds (light confirmation; the existing round-trip test already
  covers this implicitly).
- `test_read_rejects_future_minor` — planted stamp `"1.1"` raises
  matching `"not supported"`.
- `test_read_rejects_future_major` — planted stamp `"2.0"` raises
  matching `"not supported"`.

`tests/test_schema_file.py` already gates schema-file drift; after
`uv run mt5-pnl-exporter schema` it should be clean.

Coverage target stays ≥ 95%.

## Docs updates

`README.md` — the schema-stamping paragraph (currently "Schema version
stamping is a plain integer …") becomes:

> Schema version stamping is `major.minor` (`SCHEMA_VERSION = "1.0"`).
> Readers accept the same major and any minor ≤ their own; minor bumps
> add optional fields, major bumps are breaking. Consumers vendor
> `schema/snapshot.schema.json` from a specific release.

`CLAUDE.md` — two edits:

- Architecture line for `snapshot.py`: "`read()` rejects mismatched
  `SCHEMA_VERSION` (currently `2`)." → "`read()` accepts same-major
  snapshots up to its own minor (currently `\"1.0\"`); rejects others
  with a readable error."
- Gotcha: "**`SCHEMA_VERSION` is `2`** (plain integer). Major.minor
  versioning lands in Phase 1b cycle 4." → "**`SCHEMA_VERSION` is
  `\"1.0\"`** (major.minor string). `read()` accepts the same major up
  to its own minor; bump the minor for additive fields, the major for
  breaking changes."

Markdown render check (`gh api /markdown`) on README and CLAUDE.md
after edits, per the standing preference.

`docs/superpowers/specs/2026-05-31-repo-split-design.md` — no edit. The
repo-split spec already prefigures this cycle; nothing in it becomes
wrong.

## Branching and PR

Branch `phase-1b-cycle-4` from `main` (currently `2bab5dd` — the
cycle 3 merge). No direct pushes to `main`. The cycle 4 PR is **code
only**: the schema/version code, the pyproject bump, tests, and docs.

Plan ends with: commit straggling changes → push branch → open draft
PR.

## Post-merge steps (manual, gated by the human)

After the cycle 4 PR merges:

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git checkout main && git pull --ff-only
git tag -a 1.0.0 -m "1.0.0 — first stable release"
git push --tags
```

The git tag uses the package version (`1.0.0`, three components). The
schema version is independent — it's `"1.0"` (major.minor only, since
patches don't change the schema).

Then, when ready to publish (a separate, deliberate act):

```bash
uv build
uv publish   # reads UV_PUBLISH_TOKEN, or prompts
```

The first PyPI publish must be manual because PyPI trusted publishing
requires an existing project to configure against. Once `1.0` is up,
the follow-up below wires automation for subsequent releases.

## Follow-up after 1.0 publish (next PR, not this cycle)

One small chore PR after the first manual publish lands `1.0` on PyPI:

1. **GitHub Actions trusted-publish workflow.** Add
   `.github/workflows/publish.yml`: triggers on tag push matching
   `*.*.*`, uses PyPI's OIDC-based trusted publishing (no token in the
   repo). Configure the trusted publisher in PyPI's UI against the
   now-existing project. From that point onwards `git push --tags`
   triggers the publish; no human at a CLI handling tokens.
2. **`pyproject.toml` metadata polish.** Add an inline `license =
   "MIT"` (the `LICENSE` file is already in the repo), a
   `[project.urls]` table (Homepage / Issues / Repository pointing at
   the GitHub repo), and a small `classifiers = [...]` list (Python
   3.12, OS support, intended audience, topic). PyPI search and the
   project page get a tidier presentation; mypy/ruff/test surface is
   unchanged.

Bundling these in one follow-up keeps cycle 4 focused on the schema
version policy while the publishing infrastructure stabilises around
the real package on PyPI.

## Out of scope (deferred indefinitely or to a later phase)

- **Recipient-key (X25519) encryption mode, signing, traffic-layer
  hardening.** Out of scope per the parent spec.
- **Pre-1.0 migration tooling.** Greenfield repo, no users to migrate.
  Existing 0.x snapshots are throwaway.
- **New snapshot fields.** Cycle 4 is a re-stamp; the schema diff is
  the version field only.
- **CHANGELOG.md.** Considered, deferred. The git log is the source of
  truth for 1.0; if a CHANGELOG matters for 1.1+ it can land alongside
  that release.
- **Editing prior specs.** Each prior cycle's "deferred to cycle 4"
  clause matches what is landing here; no design-doc-hygiene edits
  required.
