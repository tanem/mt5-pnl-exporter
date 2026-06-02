# Phase 1b Cycle 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the `1.0` schema version policy — `SCHEMA_VERSION` becomes the string `"1.0"`, `snapshot.read()` parses the stamp as `major.minor` and accepts the same major up to its own minor, and `pyproject.toml` is bumped to `1.0.0` with the minimum metadata needed for a clean first PyPI publish. PR is code only; the git tag and `uv publish` are post-merge manual steps gated outside this plan.

**Architecture:** All the code lives in `src/mt5_pnl_exporter/snapshot.py`: three new module-level constants (`SCHEMA_VERSION`, `_MAJOR`, `_MINOR`), one new private helper (`_parse_version`), and a rewritten version check inside `read()`. The pydantic `Snapshot.schema_version` field tightens from `Literal[2]` to `Literal["1.0"]`. The schema file is regenerated. Tests live in `tests/test_snapshot.py` — six new tests plus two reworked existing ones. Three small touches to `pyproject.toml`, `README.md`, and `CLAUDE.md` round out the cycle.

**Tech Stack:** Python 3.12, pydantic 2, Typer, pytest with coverage, ruff, mypy, uv. GitHub CLI (`gh`) for the PR step and the markdown render check. Working directory throughout this plan: `/Users/tane/Code/mt5-pnl-exporter`.

**Reference spec:** [`docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md`](../specs/2026-06-02-phase-1b-cycle-4-design.md).

**Branch:** `phase-1b-cycle-4` from `main` (currently `7dd43b6`). No direct pushes to `main`.

---

## File Structure (final state)

```
src/mt5_pnl_exporter/
└── snapshot.py            # SCHEMA_VERSION: 2 → "1.0"
                           # +_MAJOR, _MINOR module constants
                           # +_parse_version helper
                           # Snapshot.schema_version: Literal[2] → Literal["1.0"]
                           # read() integer equality → major+minor range check

tests/
└── test_snapshot.py       # schema_version=2 → "1.0" (3 fixture sites)
                           # v999-planted test reworked (planted "2.0", new error string)
                           # missing-stamp test reworked (new error string)
                           # +6 tests (parse_version × 3, range check × 3)

schema/
└── snapshot.schema.json   # regenerated; the schema_version property
                           # changes from integer to string

pyproject.toml             # version: "0.1.0" → "1.0.0"
                           # description: reframed (no "Windows VPS")
                           # +readme = "README.md"

README.md                  # schema-stamping paragraph reflects "1.0" string
CLAUDE.md                  # architecture line + gotcha reflect "1.0" string

docs/superpowers/
├── specs/2026-06-02-phase-1b-cycle-4-design.md   # already on main
└── plans/2026-06-03-phase-1b-cycle-4.md          # this file
```

No new files, no new dependencies, no other modules touched.

---

## Task 1: Create the working branch and capture baseline

**Files:** none modified.

- [ ] **Step 1: Create and check out the branch**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git fetch origin
git checkout -b phase-1b-cycle-4 origin/main
git log --oneline -1
```

Expected: HEAD is `7dd43b6 docs: address cycle 4 spec review (cycle 5 split, regular PRs)` (or whatever the current tip of `main` is). Working tree clean.

- [ ] **Step 2: Run the baseline test suite + lint + format + mypy**

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: 77 tests pass, coverage ≥ 95% (~98.38%). All four gates clean. If any gate is dirty on a clean main, stop and report — fix that first before touching cycle 4 code.

---

## Task 2: `snapshot.py` — string version stamp + range-check reader (+ tests + regenerated schema)

**Files:**
- Modify: `src/mt5_pnl_exporter/snapshot.py`
- Modify: `tests/test_snapshot.py`
- Regenerate: `schema/snapshot.schema.json`

This task lands the entire schema-version policy change in one TDD-driven commit. The code, the tests, and the regenerated schema file ship together so the `tests/test_schema_file.py` drift check stays green at every commit boundary.

### Phase 2A: TDD `_parse_version` helper

- [ ] **Step 1: Add the three failing tests for `_parse_version`**

Append to `tests/test_snapshot.py` (the import block at the top already pulls from `mt5_pnl_exporter.snapshot` — extend that import in the next step):

```python
def test_parse_version_accepts_major_minor():
    assert _parse_version("1.0") == (1, 0)
    assert _parse_version("2.7") == (2, 7)


def test_parse_version_rejects_non_string():
    with pytest.raises(ValueError, match="must be a string"):
        _parse_version(2)


def test_parse_version_rejects_wrong_shape():
    for bad in ("1", "1.0.0", "1.a", ""):
        with pytest.raises(ValueError, match="major.minor"):
            _parse_version(bad)
```

Then extend the existing `from mt5_pnl_exporter.snapshot import (...)` block in `tests/test_snapshot.py` to include `_parse_version` alongside the other names. The final import block reads:

```python
from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
    _parse_version,
    read,
    write,
)
```

- [ ] **Step 2: Run the new tests and confirm they fail**

```bash
uv run pytest tests/test_snapshot.py -k parse_version -v
```

Expected: ImportError at collection time (`cannot import name '_parse_version' from 'mt5_pnl_exporter.snapshot'`). That's the red signal — the helper does not exist yet.

- [ ] **Step 3: Add the three new constants and the `_parse_version` helper**

In `src/mt5_pnl_exporter/snapshot.py`, replace the line:

```python
SCHEMA_VERSION = 2
```

with:

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

Place the constants and helper directly above the existing `_MISSING_PASSPHRASE_MSG` constant (or wherever the original `SCHEMA_VERSION` line lives — keep the location).

- [ ] **Step 4: Re-run the parse_version tests**

```bash
uv run pytest tests/test_snapshot.py -k parse_version -v
```

Expected: 3 PASS. `_parse_version` is now importable and behaves per spec.

### Phase 2B: Tighten `Snapshot.schema_version` literal + update fixtures

At this point the snapshot tests in `test_snapshot.py` still construct `Snapshot(schema_version=2, ...)`. Changing the Literal first will break those tests with pydantic validation errors, so the fixture updates and the model change land together.

- [ ] **Step 5: Update `Snapshot.schema_version` literal**

In `src/mt5_pnl_exporter/snapshot.py`, change:

```python
class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2]
    ...
```

to:

```python
class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["1.0"]
    ...
```

- [ ] **Step 6: Update the three `schema_version=2` fixture sites in `tests/test_snapshot.py`**

Three replacements (the exact line numbers may shift as the file evolves; identify by surrounding context):

1. Inside `_minimal_snapshot()` (near the top of the test module's fixture block):
   - `        schema_version=2,` → `        schema_version="1.0",`
2. Inside `test_empty_collections_roundtrip`:
   - `        schema_version=2,` → `        schema_version="1.0",`
3. Inside `test_write_failure_leaves_destination_unchanged`:
   - `        schema_version=2,` → `        schema_version="1.0",`

Use `git grep -n "schema_version=2" tests/` to confirm exactly three matches before and zero after.

- [ ] **Step 7: Run the full suite and confirm only the version-rejection tests fail**

```bash
uv run pytest
```

Expected: parse_version tests pass; round-trip and empty-collections tests pass (because the fixtures and the Literal now agree); the two existing version-rejection tests (`test_read_rejects_wrong_schema_version_after_decrypt`, `test_read_rejects_missing_schema_version_after_decrypt`) still pass — the old integer-equality check in `read()` still rejects `999` and missing keys. The schema-file drift test (`tests/test_schema_file.py`) FAILS — the model literal changed but the schema file on disk hasn't been regenerated yet. That's the red signal that phase 2C is next.

### Phase 2C: Range-check reader + rework existing tests + add range tests

- [ ] **Step 8: Add the two new range tests**

Append to `tests/test_snapshot.py`:

```python
def test_read_rejects_future_minor(tmp_path):
    """Stamp from a newer minor (1.1) is rejected by a 1.0 reader."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "1.1",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)


def test_read_rejects_future_major(tmp_path):
    """Stamp from a newer major (2.0) is rejected by a 1.0 reader."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "2.0",
        "generated_at": "2025-01-01T00:00:00Z",
        "accounts": [],
        "closed_deals": [],
        "open_positions": [],
        "cash_flows": [],
    }
    raw = json.dumps(payload).encode()
    encrypted = pyrage.passphrase.encrypt(gzip.compress(raw), PASSPHRASE)
    snap_path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)
```

- [ ] **Step 9: Rework the two existing version-rejection tests**

In `tests/test_snapshot.py`:

(a) `test_read_rejects_wrong_schema_version_after_decrypt` — change the planted stamp and the assertion match. Current:

```python
def test_read_rejects_wrong_schema_version_after_decrypt(tmp_path):
    """Encrypt a v999-tagged blob, read it, expect the schema_version rejection."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": 999,
        ...
    }
    ...
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path, PASSPHRASE)
```

becomes:

```python
def test_read_rejects_wrong_schema_version_after_decrypt(tmp_path):
    """Encrypt a v2.0-tagged blob, read it, expect the unsupported-version rejection."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    payload = {
        "schema_version": "2.0",
        ...
    }
    ...
    with pytest.raises(ValueError, match="not supported"):
        read(snap_path, PASSPHRASE)
```

(Keep the body's other fields — generated_at, accounts, closed_deals, open_positions, cash_flows — unchanged.)

(b) `test_read_rejects_missing_schema_version_after_decrypt` — change the assertion match. The missing key now routes through `_parse_version(None)`, which raises with `"must be a string"`. Current:

```python
    with pytest.raises(ValueError, match="schema_version"):
        read(snap_path, PASSPHRASE)
```

becomes:

```python
    with pytest.raises(ValueError, match="must be a string"):
        read(snap_path, PASSPHRASE)
```

- [ ] **Step 10: Add the light round-trip confirmation test**

Append to `tests/test_snapshot.py`:

```python
def test_read_accepts_exact_current_version(tmp_path):
    """Sanity: a 1.0 stamp round-trips without rejection."""
    snap_path = tmp_path / "snapshot.json.gz.age"
    write(snap_path, _minimal_snapshot(), PASSPHRASE)
    result = read(snap_path, PASSPHRASE)
    assert result.schema_version == "1.0"
```

(This is largely covered by the existing `test_write_read_roundtrip_all_record_types`, but the spec calls for it as an explicit, narrower confirmation.)

- [ ] **Step 11: Run the suite and confirm the four reader tests fail**

```bash
uv run pytest tests/test_snapshot.py -k "rejects_future or rejects_wrong or rejects_missing or accepts_exact" -v
```

Expected: the two new `test_read_rejects_future_*` tests FAIL (current `read()` raises the old message; they expect `"not supported"`), the two reworked tests FAIL (they now expect `"not supported"` and `"must be a string"` respectively), and `test_read_accepts_exact_current_version` PASSES (no reader change yet; round-trip still works). That's the red signal for the read() change.

- [ ] **Step 12: Replace the version check inside `read()`**

In `src/mt5_pnl_exporter/snapshot.py`, locate the current block (immediately after the JSON-decode try/except):

```python
    version = raw.get("schema_version", 0)
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Snapshot schema_version {version} != expected {SCHEMA_VERSION}. "
            "Re-run 'mt5-pnl-exporter poll' to regenerate."
        )
    return Snapshot.model_validate(raw)
```

Replace with:

```python
    file_major, file_minor = _parse_version(raw.get("schema_version"))
    if file_major != _MAJOR or file_minor > _MINOR:
        raise ValueError(
            f"Snapshot schema_version {raw.get('schema_version')!r} is not "
            f"supported by this reader (accepts {_MAJOR}.0–{_MAJOR}.{_MINOR}). "
            "Upgrade mt5-pnl-exporter, or re-run 'poll' on a compatible host."
        )
    return Snapshot.model_validate(raw)
```

- [ ] **Step 13: Re-run the reader tests**

```bash
uv run pytest tests/test_snapshot.py -k "rejects_future or rejects_wrong or rejects_missing or accepts_exact" -v
```

Expected: all five PASS.

### Phase 2D: Regenerate the schema file

- [ ] **Step 14: Regenerate `schema/snapshot.schema.json`**

```bash
uv run mt5-pnl-exporter schema
```

Expected: command exits 0. The diff in `schema/snapshot.schema.json` should affect only the `schema_version` property — `"type": "integer"` with `"const": 2` becomes `"type": "string"` with `"const": "1.0"` (pydantic's representation of `Literal["1.0"]`).

Inspect:

```bash
git diff schema/snapshot.schema.json
```

Expected: a small focused diff in the `schema_version` property block only. No other property changes. If anything else moved, stop and investigate — the model surface should be otherwise unchanged.

- [ ] **Step 15: Run the full suite, lint, format check, mypy**

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: 77 + 6 new = 83 tests pass; coverage ≥ 95%; ruff check clean; ruff format clean; mypy clean. If `ruff format --check` complains, run `uv run ruff format src/ tests/` and re-check.

- [ ] **Step 16: Commit**

```bash
git add src/mt5_pnl_exporter/snapshot.py tests/test_snapshot.py schema/snapshot.schema.json
git commit -m "feat(snapshot): major.minor version stamp + range-check reader

SCHEMA_VERSION moves from int 2 to string \"1.0\". snapshot.read() now
parses the stamp as major.minor and accepts the same major up to its
own minor; future minors and any other major are rejected with a
readable error naming the supported range.

Snapshot.schema_version field tightens from Literal[2] to
Literal[\"1.0\"]. The bespoke pre-check sits above model_validate so
the diagnostic stays friendly rather than surfacing a noisy pydantic
literal-mismatch error.

Schema file regenerated; the only property change is schema_version
moving from integer-const-2 to string-const-1.0.

Closes item 9 of phase 1b parent spec."
```

Expected: pre-commit secret-scan + ruff hooks pass; commit lands on `phase-1b-cycle-4`.

---

## Task 3: `pyproject.toml` — version 1.0.0 + neutral description + readme reference

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Make the three edits**

In `pyproject.toml`, modify the `[project]` block. Current:

```toml
[project]
name = "mt5-pnl-exporter"
version = "0.1.0"
description = "MT5 P&L exporter — polls deal history on a Windows VPS and writes snapshot.json"
authors = [
    { name = "Tane Morgan", email = "464864+tanem@users.noreply.github.com" }
]
requires-python = ">=3.12"
```

becomes:

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
```

Three changes: `version` bumps `0.1.0` → `1.0.0`; `description` drops "Windows VPS" and adds "typed, encrypted"; a new `readme = "README.md"` line. `authors`, `requires-python`, and everything else in the file (dependencies, optional-deps, scripts, build-system, dependency-groups, tool configs) is unchanged.

- [ ] **Step 2: Confirm uv reads the new metadata**

```bash
uv sync
```

Expected: `uv` reports the project as `mt5-pnl-exporter==1.0.0` (or similar — the key signal is no error and the new version). The dependency lockfile may update with a version metadata line; that's fine.

- [ ] **Step 3: Run the suite (no regressions expected — pyproject changes don't touch code)**

```bash
uv run pytest
```

Expected: 83 tests pass, coverage ≥ 95%.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: pyproject bump to 1.0.0 for first PyPI publish

Three edits to the [project] block:

- version 0.1.0 → 1.0.0
- description drops 'Windows VPS' framing and adds 'typed, encrypted'
- readme = 'README.md' so PyPI renders the README on the project page

Author block stays as-is (matches LICENSE and the git author). License
field, project URLs, and classifiers land in the follow-up PR
alongside the GitHub Actions trusted-publish workflow."
```

(Stage `uv.lock` if `uv sync` updated it; if `uv sync` made no changes, just stage `pyproject.toml`.)

Expected: pre-commit hooks pass; commit lands on `phase-1b-cycle-4`.

---

## Task 4: README + CLAUDE.md — reflect the "1.0" stamp format

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the README schema-stamping paragraph**

In `README.md`, locate the paragraph currently reading:

> Schema version stamping is a plain integer (`SCHEMA_VERSION = 2`) in 0.x.
> `major.minor` versioning ships in the 1.0 release (Phase 1b cycle 4).

Replace with:

> Schema version stamping is `major.minor` (`SCHEMA_VERSION = "1.0"`). Readers accept the same major and any minor ≤ their own; minor bumps add optional fields, major bumps are breaking. Consumers vendor `schema/snapshot.schema.json` from a specific release.

- [ ] **Step 2: Update the CLAUDE.md architecture line for `snapshot.py`**

In `CLAUDE.md`, locate the bullet under `## Architecture` that begins with `` - `snapshot.py` — typed pydantic models for ...``. Inside that bullet, find the substring:

> `read()` rejects mismatched `SCHEMA_VERSION` (currently `2`).

Replace with:

> `read()` accepts same-major snapshots up to its own minor (currently `"1.0"`); rejects others with a readable error.

Leave the rest of that bullet unchanged.

- [ ] **Step 3: Update the CLAUDE.md `SCHEMA_VERSION` gotcha**

In `CLAUDE.md`, under `## Gotchas`, locate the bullet that currently reads:

> **`SCHEMA_VERSION` is `2`** (plain integer). Major.minor versioning lands in Phase 1b cycle 4.

Replace with:

> **`SCHEMA_VERSION` is `"1.0"`** (major.minor string). `read()` accepts the same major up to its own minor; bump the minor for additive fields, the major for breaking changes.

- [ ] **Step 4: Run the markdown render check on README**

```bash
cat README.md | jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' \
  | gh api /markdown --input - > /tmp/cycle4-readme-rendered.html
grep -E -o '<h[1-6][^>]*>[^<]*' /tmp/cycle4-readme-rendered.html
```

Expected: heading list unchanged from cycle 3's render (`mt5-pnl-exporter`, `Install`, `Quick start`, `Commands`, `Schema`, `Snapshot size`, `Threat model`, `What's protected`, `What's not protected`, `Transport guidance`, `Status`). If the heading list shifts, stop and investigate — the schema-stamping paragraph edit shouldn't introduce or remove any heading. Visual-only concerns (line-break behaviour) are flagged in the task report for human review rather than auto-fixed.

- [ ] **Step 5: Run the markdown render check on CLAUDE.md**

```bash
cat CLAUDE.md | jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' \
  | gh api /markdown --input - > /tmp/cycle4-claude-rendered.html
grep -E -o '<h[1-6][^>]*>[^<]*' /tmp/cycle4-claude-rendered.html
```

Expected: headings unchanged (`CLAUDE.md`, `Commands`, `Architecture`, `Gotchas`, `Conventions`). The edits are in-place; no structural change.

- [ ] **Step 6: Run the suite to confirm no regressions**

```bash
uv run pytest
```

Expected: 83 tests pass, coverage ≥ 95%.

- [ ] **Step 7: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: README + CLAUDE.md reflect 1.0 major.minor stamp

README's schema-stamping paragraph drops the 'plain integer' framing
and names the range-acceptance rule. CLAUDE.md's architecture line for
snapshot.py and the SCHEMA_VERSION gotcha pick up the same wording.

No structural changes in either doc — only the lines that referenced
the integer stamp."
```

Expected: commit lands on `phase-1b-cycle-4`.

---

## Task 5: Final verification, push, open PR

**Files:** none modified.

- [ ] **Step 1: Full quality-gate sweep**

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/mt5_pnl_exporter
```

Expected: 83 tests pass with coverage ≥ 95%; all three lint/format/mypy gates clean.

- [ ] **Step 2: Schema staleness check**

```bash
uv run mt5-pnl-exporter schema && git diff --stat schema/snapshot.schema.json
```

Expected: no diff. (The Task 2 commit already regenerated the schema; this re-confirms.)

- [ ] **Step 3: Review the branch shape**

```bash
git status
git log --oneline main..HEAD
```

Expected: working tree clean; three commits on the branch ahead of `main`:

```
<sha3> docs: README + CLAUDE.md reflect 1.0 major.minor stamp
<sha2> build: pyproject bump to 1.0.0 for first PyPI publish
<sha1> feat(snapshot): major.minor version stamp + range-check reader
```

- [ ] **Step 4: Push the branch**

```bash
git push -u origin phase-1b-cycle-4
```

Expected: branch published; tracking `origin/phase-1b-cycle-4`.

- [ ] **Step 5: Open the PR (regular, not draft)**

```bash
gh pr create --base main --head phase-1b-cycle-4 \
  --title "Phase 1b cycle 4: major.minor version policy + 1.0.0 pyproject" \
  --body "$(cat <<'EOF'
## Summary
- `SCHEMA_VERSION` moves from `int = 2` to `str = "1.0"`. `snapshot.read()` now parses the stamp as `major.minor` and accepts the same major up to its own minor; everything else is rejected with a readable error naming the supported range.
- `Snapshot.schema_version` field tightens from `Literal[2]` to `Literal["1.0"]`; schema file regenerated (only the `schema_version` property changes — integer → string).
- `pyproject.toml` bumps to `1.0.0`, drops "Windows VPS" framing in the description, and adds `readme = "README.md"` so PyPI renders the README on the project page.
- README and CLAUDE.md updated to reflect the new stamp format.

Code only. Git tag (`1.0.0`) and the first `uv publish` are deliberate post-merge steps — and they wait for cycle 5 (pre-publish docs polish) to merge first.

See [`docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md`](docs/superpowers/specs/2026-06-02-phase-1b-cycle-4-design.md)
and [`docs/superpowers/plans/2026-06-03-phase-1b-cycle-4.md`](docs/superpowers/plans/2026-06-03-phase-1b-cycle-4.md).

## Test plan
- [x] `uv run pytest` passes with coverage ≥ 95%
- [x] `uv run ruff check src/ tests/` clean
- [x] `uv run ruff format --check src/ tests/` clean
- [x] `uv run mypy src/mt5_pnl_exporter` clean
- [x] `schema/snapshot.schema.json` regenerated; only the `schema_version` property changed
- [x] README + CLAUDE.md render cleanly via `gh api /markdown`
EOF
)"
```

Expected: `gh pr create` returns a PR URL. Report the URL back to the user. The PR opens ready for review (no draft flag).

---

## Self-Review (completed before saving)

**Spec coverage:**

- `SCHEMA_VERSION` becomes `"1.0"` → Task 2, Step 3.
- `snapshot.read()` range-check (major + minor ≤ code's) with readable error naming the range → Task 2, Step 12.
- `Snapshot.schema_version: Literal["1.0"]` → Task 2, Step 5.
- Schema file regenerated → Task 2, Step 14; reconfirmed Task 5, Step 2.
- `pyproject.toml` version bump + neutral description + `readme = "README.md"`; `authors` unchanged → Task 3.
- README schema-stamping paragraph rewrite → Task 4, Step 1.
- CLAUDE.md architecture line + gotcha → Task 4, Steps 2–3.
- Markdown render check on both README and CLAUDE.md → Task 4, Steps 4–5.
- Six new tests (`_parse_version` × 3, range check × 3, plus the light round-trip) → Task 2, Steps 1, 8, 10.
- Two reworked existing tests (v999 → "2.0"; missing-stamp error string) → Task 2, Step 9.
- Three fixture sites updated (`schema_version=2` → `"1.0"`) → Task 2, Step 6.
- Coverage stays ≥ 95% → Task 2, Step 15; Task 5, Step 1.
- Branch `phase-1b-cycle-4` from `main`, no direct pushes → Task 1, Step 1; Task 5, Steps 4–5.
- PR is **regular, not draft** → Task 5, Step 5 (`gh pr create` without `--draft`).
- Plan ends with commit + push + PR → Task 5.

**Placeholder scan:**

- No "TBD", no "TODO", no "implement later", no "similar to Task N". Each code step shows the exact code; each command step shows the exact command and expected output. The Task 5 PR-body heredoc has no placeholders — the SHAs are filled in by `git log` at execution time per Step 3.

**Type and naming consistency:**

- `SCHEMA_VERSION: str = "1.0"`, `_MAJOR: int = 1`, `_MINOR: int = 0`, `_parse_version(stamp: object) -> tuple[int, int]` consistent across Task 2 Steps 3 and 12.
- `Snapshot.schema_version: Literal["1.0"]` consistent with the `SCHEMA_VERSION` value.
- Error message strings (`"must be a string"`, `"major.minor"`, `"not supported"`) match between Task 2 Steps 1/8/9 (test asserts) and Task 2 Steps 3/12 (raise sites).
- `_parse_version` import added to `tests/test_snapshot.py`'s existing import block in Task 2, Step 1.
