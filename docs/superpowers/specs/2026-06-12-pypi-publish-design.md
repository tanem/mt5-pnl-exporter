# PyPI publish readiness — design

Date: 2026-06-12
Status: approved

## Goal

Publish `mt5-pnl-exporter` to PyPI as version `1.0.0`. The package already
builds and installs cleanly; this work fills the packaging-metadata gaps and
adds the release mechanics. No source or runtime code changes.

## Verified preconditions

These were checked before writing this spec and require no further action:

- `uv build` produces `mt5_pnl_exporter-1.0.0` sdist + wheel.
- Wheel contents are correct: all modules, `py.typed`, and `entry_points.txt`
  are present.
- The root-level `schema/snapshot.schema.json` is correctly **absent** from the
  wheel. The `schema` command regenerates it from the pydantic model at runtime
  (`cli.py`); nothing reads the file at runtime, so it does not belong in the
  wheel.
- A clean-venv install resolves the `mt5-pnl-exporter` entry point; `--help` and
  `schema` run.
- `twine check` passes on both artifacts (README renders as the PyPI
  description).
- The name `mt5-pnl-exporter` is free on PyPI (404 on the JSON API).

## Decisions

| Topic | Decision |
| --- | --- |
| PyPI authentication | Trusted Publishing (OIDC) — no stored API token |
| Release trigger | Published GitHub Release |
| TestPyPI | Manual `workflow_dispatch` path to a TestPyPI trusted publisher, for a one-time rehearsal |
| Action pins | SHA-pin the new workflow **and** reconcile `ci.yml`'s tag pins to SHAs, all Renovate-managed |
| Licence metadata | PEP 639 SPDX (`license = "MIT"` + `license-files`), no `License ::` classifier |
| OS classifier | `Operating System :: Microsoft :: Windows` (the `export` command is Windows-only) |

## Scope

Two deliverables plus a CI guard, in a single PR:

1. Packaging metadata in `pyproject.toml`.
2. A release workflow at `.github/workflows/release.yml`.
3. A CI guard (`uv build` + `twine check`) and the `ci.yml` pin reconciliation.

Out of scope: any change to `src/` or runtime behaviour.

## 1. Packaging metadata (`pyproject.toml`)

Add to the `[project]` table:

- `license = "MIT"` and `license-files = ["LICENSE"]` (PEP 639). Do **not** add a
  `License ::` classifier — under PEP 639 the SPDX expression and the licence
  classifier are mutually exclusive.
- `keywords = ["metatrader", "mt5", "trading", "forex", "pnl", "snapshot"]`.
- `classifiers`:
  - `Development Status :: 5 - Production/Stable`
  - `Programming Language :: Python :: 3`
  - `Programming Language :: Python :: 3.12`
  - `Operating System :: Microsoft :: Windows`
  - `Intended Audience :: Financial and Insurance Industry`
  - `Topic :: Office/Business :: Financial :: Investment`
  - `Environment :: Console`
  - `Typing :: Typed`

Add a `[project.urls]` table:

- `Homepage = "https://github.com/tanem/mt5-pnl-exporter"`
- `Repository = "https://github.com/tanem/mt5-pnl-exporter"`
- `Issues = "https://github.com/tanem/mt5-pnl-exporter/issues"`
- `Changelog = "https://github.com/tanem/mt5-pnl-exporter/releases"`

The version stays `1.0.0`.

## 2. Release workflow (`.github/workflows/release.yml`)

One workflow file, triggered on both:

```yaml
on:
  release:
    types: [published]
  workflow_dispatch:
```

Three jobs:

- **`build`** (always runs): checks out, sets up `uv`, runs `uv build`, uploads
  `dist/` as a workflow artifact. Single source of truth for the artifacts both
  publish jobs consume.
- **`publish-testpypi`**: `if: github.event_name == 'workflow_dispatch'`.
  `environment: testpypi`, `permissions: { id-token: write }`. Downloads the
  artifact and publishes to `https://test.pypi.org/legacy/` via OIDC.
- **`publish-pypi`**: `if: github.event_name == 'release'`.
  `environment: pypi`, `permissions: { id-token: write }`. Downloads the artifact
  and publishes to PyPI via OIDC.

Both publish jobs `needs: build` and use `pypa/gh-action-pypi-publish`
(SHA-pinned). The build is reused; the trigger decides the destination. Binding
each publish job to a GitHub Environment gives a deployment record and a place to
attach a protection rule later if desired.

All actions are pinned to commit SHAs with a trailing `# vX.Y.Z` comment so
Renovate manages them.

### The GitHub Release is the trigger and the changelog

Because the trigger is a published GitHub Release, every PyPI version has a
matching Release on the repo's Releases page — this is not an optional extra, it
is the mechanism. The release flow is:

1. Create the tag `v1.0.0`.
2. Draft a GitHub Release against that tag, with notes.
3. Publish it. The `release: published` event fires `release.yml`, which builds
   and uploads to PyPI.

This is standard practice for well-regarded Python libraries (for example
`httpx`, `rich`, `pydantic`): each PyPI version maps to a GitHub Release whose
notes serve as the changelog. It is why the `Changelog` project URL points at
`/releases`.

## 3. CI guard and pin reconciliation (`.github/workflows/ci.yml`)

- Add `twine` to the `dev` dependency group and add a CI step (after the
  existing checks): `uv build`, then `uv run twine check --strict dist/*`. A
  broken README or invalid metadata then fails CI before a release, matching the
  repo's existing "CI catches drift" approach (`tests/test_schema_file.py`).
  `twine` is a lockfile-pinned dev dependency rather than an ephemeral `uvx`
  tool, so it is reproducible and Renovate-managed like every other dependency
  in the repo — a new twine release arrives as a reviewable PR, not a silent CI
  behaviour change.
- Reconcile `ci.yml`'s tag pins (`actions/checkout@v6`, `setup-python@v6`,
  `setup-uv@v7`, `codecov-action@v6`) to commit SHAs with trailing version
  comments. The new `release.yml` is SHA-pinned the same way from the start.

## 4. Manual prerequisites (out-of-band)

These are one-time web-UI steps the workflow cannot perform. The implementation
plan records them; the user performs them.

- **PyPI** — register a pending publisher:
  - Owner: `tanem`
  - Repository: `mt5-pnl-exporter`
  - Workflow filename: `release.yml`
  - Environment: `pypi`
- **TestPyPI** — register the same pending publisher with environment
  `testpypi`.
- **GitHub** — create the `pypi` and `testpypi` Environments on the repo.

## 5. Rollout sequence

1. Merge the metadata + workflow PR.
2. Register the pending publishers on PyPI and TestPyPI; create the two GitHub
   Environments.
3. Run `release.yml` via `workflow_dispatch` → TestPyPI. Confirm the OIDC
   handshake works and the page renders.
4. Draft and publish the GitHub Release `v1.0.0` → PyPI.

## Risks and notes

- `1.0.0` is **immutable** once uploaded to PyPI; the version number cannot be
  reused. The TestPyPI rehearsal de-risks the first real upload.
- Publishing `1.0.0` signals a stable API. This is consistent with how the README
  already presents the snapshot as a stable contract.
- Documentation: after the change, update `CLAUDE.md` and `README.md` per the
  repo convention (the `## Commands` and dependency/Renovate notes may reference
  the release workflow). The README already carries a PyPI badge and
  `uv tool install` instructions, so no install-section rewrite is needed.

## Testing

Workflows are not unit-testable here. Confidence comes from:

- The CI guard (`uv build` + `twine check`) on every PR and push.
- The TestPyPI dispatch run as a live rehearsal of the full publish path before
  the first real release.

No changes to the existing test suite (still 100% coverage, `mypy --strict`,
ruff).