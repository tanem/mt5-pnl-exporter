# Phase 1b cycle 6: Codecov upload, coverage badge, 100% floor

Status: design. Ready to plan implementation once approved.

Refines the "Out of scope (deferred to cycle 6 …)" subsection of
[`2026-06-03-phase-1b-cycle-5-design.md`](2026-06-03-phase-1b-cycle-5-design.md).
Lands the final gate before the `1.0.0` tag: a Codecov upload step in
CI, a coverage badge in the README badge row, and a bump of the local
coverage floor from 95% to 100%. Last cycle of Phase 1b; tag and
publish follow as manual post-merge steps.

## Why

Three threads land together because they all touch the same surface —
coverage — and the 1.0 tag is the natural moment to settle each:

- **Codecov upload.** `ci.yml` already runs `pytest --cov-report=xml`,
  so the coverage file is produced on every push and PR — but nothing
  consumes it. Codecov adds a diff-coverage comment on each PR, which
  is the load-bearing feedback for a project that enforces a hard
  floor. The pattern is already proven:
  `mt5-pnl/.github/workflows/ci.yml:24-27` runs the same step against
  the same action against the same token name; cycle 6 ports it
  verbatim with the slug swapped.
- **README badge.** First-time visitors get the same one-glance signal
  that the `tests` and `PyPI` badges already carry. The badge slot is
  the only one in the cycle 5 badge row that hasn't been filled.
- **Floor bumped to 100%.** The current `--cov-fail-under=95` was
  inherited from `mt5-pnl` at port time (commit `341cc1f`, set when
  coverage was *actually* 95%). Real coverage has since drifted up
  to 98.42%; the gap to 100% is four statements in `cli.py` (the
  uncovered `schema` command body) plus five partial branches on
  `DataSource` Protocol stubs (un-callable by design). A small,
  honest closure is cheaper than letting the floor lag reality
  through the 1.0 tag — and locks in the property going forward.

The tag and the publish wait on this cycle per cycle 5's post-merge
sequence — once cycle 6 is on `main`, the `1.0.0` git tag and the
first `uv publish` proceed.

## Deliverables

Five deliverables, all in one PR.

1. **`ci.yml`** — append a `codecov/codecov-action@v5` step after the
   existing `pytest --cov-report=xml` line.
2. **`README.md`** — insert a coverage badge between the `tests` and
   `PyPI` badges in the badge row.
3. **`pyproject.toml`** — bump `--cov-fail-under=95` to
   `--cov-fail-under=100` in `[tool.pytest.ini_options]`, and add a
   coverage-report exclude pattern for inline-`...` Protocol stubs.
4. **`tests/test_cli.py`** — add one test that exercises the `schema`
   subcommand end-to-end, closing the four-statement gap in
   `cli.py:198-201`.
5. **`CLAUDE.md`** — one-line bump under the *Conventions* / *Tests*
   block: the coverage floor is now 100%.

Codecov is a report, not a gate. The 100% floor is enforced locally
by `pytest --cov-fail-under` and in CI by the same `pytest` invocation
that already runs.

## `ci.yml` change

Single step appended to the existing job in
`.github/workflows/ci.yml`. The current final line is
`uv run pytest --cov-report=xml`; the new step lands directly below it:

```yaml
      - uses: codecov/codecov-action@v5
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          slug: tanem/mt5-pnl-exporter
          files: ./coverage.xml
```

Three params, exactly mirroring `mt5-pnl/.github/workflows/ci.yml:24-27`
with the slug swapped from `tanem/mt5-pnl` to `tanem/mt5-pnl-exporter`.
The `coverage.xml` path matches what `pytest --cov-report=xml` writes
(repo root, per `pyproject.toml`'s pytest config).

**No `if:` gate.** The step runs on push and PR alike. PR coverage
comments are the primary value-add; gating to `push` only would
silence them.

**No fail-on-error toggle.** The action defaults to non-fatal on
upload failure, which matches the design intent — Codecov is a
report, not a gate. If the upload fails the build still passes; the
PR comment just doesn't appear that run.

**Action version pinning.** Pinned to `v5` (major), matching
`mt5-pnl`. Major-pin is fine: Codecov's v5 action follows
semver-compatible minor/patch updates and breaking changes only
ship behind a major bump.

## README badge change

The cycle 5 badge row currently reads:

```markdown
[![Licence](https://img.shields.io/github/license/tanem/mt5-pnl-exporter)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![tests](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mt5-pnl-exporter)](https://pypi.org/project/mt5-pnl-exporter/)
```

After: insert one line between `tests` and `PyPI`:

```markdown
[![coverage](https://codecov.io/gh/tanem/mt5-pnl-exporter/branch/main/graph/badge.svg)](https://codecov.io/gh/tanem/mt5-pnl-exporter)
```

Final order: Licence | Python | tests | coverage | PyPI. Groups the
two CI-result badges adjacent (tests + coverage), then package
status (PyPI). Same ordering convention as `mt5-pnl`.

The badge SVG renders empty until the first push-to-main upload
populates Codecov; the cycle 6 merge itself is that push, so the
badge fills in within a few minutes of merge.

## Manual prerequisites

Both already complete per the user (confirmed at brainstorm time):

- The `tanem/mt5-pnl-exporter` Codecov project exists at codecov.io.
- `CODECOV_TOKEN` is set as a GitHub Actions secret on the repo.

The plan will include a `gh secret list` verification step that runs
locally before push so a missing token is caught before the CI run.
No new manual steps land in this cycle.

## Closing the gap to 100%

Today's measured coverage is **98.42%** (`pytest --cov-report=term`
on `phase-1b-cycle-6` cut from `main` at `0b75140`):

```
Name                                       Stmts   Miss Branch BrPart  Cover
src/mt5_pnl_exporter/cli.py                  105      4     14      0    97%
src/mt5_pnl_exporter/sources/base.py          26      0     10      5    86%
TOTAL                                        467      4    102      5    98%
```

Two gaps. Both close with small, targeted edits — no test gymnastics,
no defensive pragmas sprinkled through real logic.

**Gap 1 — `cli.py:198-201` (the `schema` command body).**
`mt5-pnl-exporter schema` writes the generated JSON Schema to disk.
It has no test today. Closure: one test in `tests/test_cli.py` that
invokes the command via Typer's `CliRunner` against a `tmp_path`
output, then asserts the resulting file parses as JSON and contains a
top-level `"$defs"` key (proof it's the pydantic-generated schema and
not stub output). About 10 lines.

**Gap 2 — `sources/base.py:48-52` (`DataSource` Protocol stubs).**
Each line is `def method(...) -> T: ...`. Coverage flags the
`enter-method → exit` branch as never taken because the bodies
(literally `...`) are unreachable: `DataSource` is a Protocol; it's
implemented, never instantiated. Closure: one new entry in
`[tool.coverage.report] exclude_lines` matching the inline-`...`
suffix:

```toml
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "\\.\\.\\.$",   # Protocol method stubs ending in `...`
]
```

The regex `\.\.\.$` matches lines that end with literal `...` — the
Protocol-stub convention — and nothing else in the codebase
(`coverage` treats `exclude_lines` patterns as anchored within a
single line). No source-file edits.

**Floor bump.** `--cov-fail-under=95` becomes `--cov-fail-under=100`
in `pyproject.toml`'s `[tool.pytest.ini_options]`. Once the two gaps
above close, `pytest` reports 100% and the new floor holds.

**No source pragmas.** Closing gaps via `# pragma: no cover` on real
code paths would defeat the point of a 100% floor. The only exclusion
here is structural (Protocol stubs are uncallable by language design),
and it lives in `pyproject.toml`, not inline in source.

## Tests

One new test in `tests/test_cli.py`:

- `test_schema_command_writes_json_schema` — runs `mt5-pnl-exporter
  schema --output <tmp_path>/snapshot.schema.json` via `CliRunner`,
  asserts exit code 0, asserts the written file exists, parses it as
  JSON, and checks for a `"$defs"` top-level key.

The new Codecov upload step itself isn't exercised by `pytest` — it's
CI config — but its input (`coverage.xml`) is produced by the existing
`--cov-report=xml` flag, which the test suite already verifies works.

`tests/test_schema_file.py` is unaffected — no schema model edits.

Coverage target moves to **100%**, enforced locally by
`pytest --cov-fail-under=100`. Codecov reports the same percentage
on each PR but doesn't itself gate the build.

## CLAUDE.md update

One edit. The *Commands* block currently contains:

```
uv run pytest                          # tests (coverage ≥95%; schema staleness check included)
```

Becomes:

```
uv run pytest                          # tests (coverage = 100%; schema staleness check included)
```

`≥95%` → `= 100%` because the floor is now also the ceiling — any
regression below 100% fails the build. No other CLAUDE.md edits.

## Markdown render check

Per the standing preference (memory entry: "Markdown render check"),
after the README badge edit run `gh api /markdown` in gfm + repo
context against `README.md`. One render pass — README is the only
public-facing `.md` file edited in the cycle (CLAUDE.md is an internal
convention file; render-check is overkill for it).

The README change is a single new line in an existing badge row, so
visual risk is low; the render check is mostly to confirm the new
badge URL resolves and the row still flows correctly on GitHub.

## Branching and PR

Branch `phase-1b-cycle-6` from `main` (currently `0b75140`, the
cycle 5 merge). No direct pushes to `main`. PR is **regular** (not
draft) — opens ready for review immediately, per the standing
preference.

Plan ends with: commit changes → push branch → open PR.

## Post-merge: tag and publish

Once cycle 6 is on `main`, the manual tag/publish sequence from cycle
4's spec proceeds:

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git checkout main && git pull --ff-only
git tag -a 1.0.0 -m "1.0.0 — first stable release"
git push --tags
```

Then, when ready (a separate, deliberate act):

```bash
uv build
uv publish   # reads UV_PUBLISH_TOKEN, or prompts
```

The git tag uses the package version (`1.0.0`, three components). The
schema version stays at `"1.0"` (major.minor only — patch versions of
the package can ship without a schema bump).

After the first successful publish, the follow-up PR from cycle 4's
spec lands: GHA trusted-publish workflow, `pyproject` classifiers /
urls / inline `license = "MIT"`. That work is not part of cycle 6.

## Out of scope (deferred to the post-publish follow-up or later)

- **GHA trusted-publish workflow.** Needs the project to exist on
  PyPI to configure the trusted publisher — post-first-publish
  follow-up PR.
- **`pyproject` metadata polish** (`license = "MIT"` inline,
  `[project.urls]`, `classifiers = [...]`). Same follow-up PR.
- **Per-file coverage gates and a `codecov.yml`.** The floor is
  whole-package (`--cov-fail-under=100`); Codecov runs with its
  defaults — no `codecov.yml` in this cycle. Per-file gating and a
  bespoke Codecov config become worthwhile only if a real
  multi-package divergence appears.
- **Editing prior specs.** Cycle 5's spec already accounts for cycle 6
  in its post-merge sequence; cycle 4's spec was edited in a
  follow-up commit (`87c8811`) to do the same. No design-doc-hygiene
  edits land in this cycle.
