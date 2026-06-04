# Phase 1b cycle 6: Codecov upload + coverage badge

Status: design. Ready to plan implementation once approved.

Refines the "Out of scope (deferred to cycle 6 …)" subsection of
[`2026-06-03-phase-1b-cycle-5-design.md`](2026-06-03-phase-1b-cycle-5-design.md).
Lands the final gate before the `1.0.0` tag: a Codecov upload step in
CI and a coverage badge in the README badge row. Last cycle of Phase
1b; tag and publish follow as manual post-merge steps.

## Why

`ci.yml` already runs `pytest --cov-report=xml`, so the coverage file
is produced on every push and PR — but nothing consumes it. Codecov
gives two things the project doesn't currently have:

- **A coverage trend visible on PRs.** Codecov comments diff coverage
  on each PR, which is the load-bearing feedback for a project that
  enforces a 95% floor.
- **A coverage badge for the README.** First-time visitors get the
  same one-glance signal that the `tests` and `PyPI` badges already
  carry. The badge slot is the only one in the cycle 5 badge row that
  hasn't been filled.

The pattern is already proven: `mt5-pnl/.github/workflows/ci.yml:24-27`
runs the same upload step against the same Codecov action against the
same token name. Cycle 6 ports that pattern verbatim with the slug
swapped.

The tag and the publish wait on this cycle per cycle 5's post-merge
sequence — once cycle 6 is on `main`, the `1.0.0` git tag and the
first `uv publish` proceed.

## Deliverables

Three deliverables, all in one PR.

1. **`ci.yml`** — append a `codecov/codecov-action@v5` step after the
   existing `pytest --cov-report=xml` line.
2. **`README.md`** — insert a coverage badge between the `tests` and
   `PyPI` badges in the badge row.
3. **No other changes** — no CLAUDE.md edit, no test changes, no
   `pyproject` touch, no threshold change. Coverage stays at 95%
   enforced locally by `pytest --cov-fail-under`; Codecov is a report,
   not a gate.

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

## Tests

No new tests. The change is CI-config + a Markdown badge — neither is
exercised by `pytest`. The existing `pytest --cov-report=xml` line
already produces the file the action consumes; if that line ever
broke, the test suite would fail first.

`tests/test_schema_file.py` is unaffected — no schema model edits.

Coverage target stays ≥ 95%, enforced by the local
`pytest --cov-fail-under` config. Codecov reports the same percentage
but doesn't gate the build.

## Markdown render check

Per the standing preference (memory entry: "Markdown render check"),
after the README badge edit run `gh api /markdown` in gfm + repo
context against `README.md`. One render pass — the only edited `.md`
file in the cycle.

The change is a single new line in an existing badge row, so visual
risk is low; the render check is mostly to confirm the new badge
URL resolves and the row still flows correctly on GitHub.

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
- **Coverage threshold tuning.** 95% stays. Any bump or relaxation is
  a separate decision driven by real coverage data, not by this
  cycle.
- **Per-file coverage gates / `codecov.yml`.** No custom Codecov
  config file in this cycle. Defaults are fine for a single-package
  repo; revisit if/when the project sprouts multiple packages.
- **Branch-coverage reporting.** `pyproject.toml`'s pytest config
  governs what's collected; adding branch coverage is a separate
  decision, not coupled to the Codecov upload.
- **Editing prior specs.** Cycle 5's spec already accounts for cycle 6
  in its post-merge sequence; cycle 4's spec was edited in a
  follow-up commit (`87c8811`) to do the same. No design-doc-hygiene
  edits land in this cycle.
