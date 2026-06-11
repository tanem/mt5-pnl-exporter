# PyPI Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `mt5-pnl-exporter` publishable to PyPI as `1.0.0` by adding packaging metadata, a Trusted-Publishing release workflow, and a CI metadata guard.

**Architecture:** Three config changes plus docs. `pyproject.toml` gains PEP 639 licence metadata, project URLs, classifiers, keywords, and a `twine` dev dependency. A new `release.yml` builds once and publishes to PyPI on a published GitHub Release (or to TestPyPI on manual dispatch) via OIDC — no stored token. `ci.yml` gains a `twine check` guard and has its action tags reconciled to commit SHAs. No `src/` or runtime changes.

**Tech Stack:** uv (build + run), uv_build backend, twine, GitHub Actions, PyPI Trusted Publishing (`pypa/gh-action-pypi-publish`).

**Reference spec:** [`docs/superpowers/specs/2026-06-12-pypi-publish-design.md`](../specs/2026-06-12-pypi-publish-design.md)

---

## File map

- Modify: `pyproject.toml` — licence/url/classifier/keyword metadata + `twine` dev dep (Task 1).
- Modify: `.github/workflows/ci.yml` — `twine check` guard + SHA pins (Task 2).
- Create: `.github/workflows/release.yml` — build + publish workflow (Task 3).
- Modify: `CONTRIBUTING.md`, `CLAUDE.md` — release process + packaging corrections (Task 4).
- No change: `README.md` (PyPI badge and `uv tool install` instructions already present), `src/`.

## Pinned action SHAs (used in Tasks 2 and 3)

Resolved 2026-06-12. Renovate will keep these current after merge.

| Action | Pin line |
| --- | --- |
| actions/checkout | `actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3` |
| actions/setup-python | `actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0` |
| astral-sh/setup-uv | `astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7.6.0` |
| codecov/codecov-action | `codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f # v6.0.2` |
| actions/upload-artifact | `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2` |
| actions/download-artifact | `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0` |
| pypa/gh-action-pypi-publish | `pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # v1.14.0` |

---

## Task 1: Packaging metadata + twine dev dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add metadata fields to the `[project]` table**

In `pyproject.toml`, find the line `requires-python = ">=3.12"` and insert the new fields immediately after it (before `dependencies = [`):

```toml
requires-python = ">=3.12"
license = "MIT"
license-files = ["LICENSE"]
keywords = ["metatrader", "mt5", "trading", "forex", "pnl", "snapshot"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Operating System :: Microsoft :: Windows",
    "Intended Audience :: Financial and Insurance Industry",
    "Topic :: Office/Business :: Financial :: Investment",
    "Environment :: Console",
    "Typing :: Typed",
]
```

Do **not** add a `License ::` classifier — under PEP 639 the SPDX `license` expression and a licence classifier are mutually exclusive.

- [ ] **Step 2: Add the `[project.urls]` table**

Find the `[project.scripts]` table:

```toml
[project.scripts]
mt5-pnl-exporter = "mt5_pnl_exporter.cli:app"
```

Insert a new `[project.urls]` table immediately after it:

```toml
[project.urls]
Homepage = "https://github.com/tanem/mt5-pnl-exporter"
Repository = "https://github.com/tanem/mt5-pnl-exporter"
Issues = "https://github.com/tanem/mt5-pnl-exporter/issues"
Changelog = "https://github.com/tanem/mt5-pnl-exporter/releases"
```

- [ ] **Step 3: Add `twine` to the dev dependency group**

Find the `[dependency-groups]` table:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-cov>=5",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-PyYAML>=6",
    "pre-commit>=4",
]
```

Add `"twine>=6.1",` to the `dev` list (the `>=6.1` lower bound ensures Metadata-Version 2.4 / PEP 639 support):

```toml
dev = [
    "pytest>=9.0.3",
    "pytest-cov>=5",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-PyYAML>=6",
    "pre-commit>=4",
    "twine>=6.1",
]
```

- [ ] **Step 4: Sync the environment**

Run: `uv sync`
Expected: completes without error; `twine` appears in the resolved packages (first run) and `uv.lock` is updated.

- [ ] **Step 5: Build and validate the metadata**

Run: `rm -rf dist && uv build && uv run twine check --strict dist/*`
Expected: `Successfully built .../mt5_pnl_exporter-1.0.0.tar.gz` and `...-1.0.0-py3-none-any.whl`, then both lines report `PASSED`.

If `uv build` errors on `license` or `license-files`, the `uv_build` backend version is too old for PEP 639 — stop and report; do not work around it (it would fight Renovate's pin).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add PyPI packaging metadata and twine check tooling"
```

---

## Task 2: CI metadata guard + SHA-pin reconciliation

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Reconcile the action pins to SHAs**

In `ci.yml`, replace the four tag-pinned `uses:` lines with their SHA-pinned equivalents (keep the surrounding `with:` blocks unchanged):

```yaml
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7.6.0
```

and the codecov step:

```yaml
      - uses: codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f # v6.0.2
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          slug: tanem/mt5-pnl-exporter
          files: ./coverage.xml
```

- [ ] **Step 2: Add the packaging guard step**

In `ci.yml`, find the test step `- run: uv run pytest --cov-report=xml`. Insert these two steps immediately after it (before the codecov step):

```yaml
      - run: uv build
      - run: uv run twine check --strict dist/*
```

- [ ] **Step 3: Validate the workflow YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output, exit code 0 (file is valid YAML).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add twine check guard and pin actions to SHAs"
```

---

## Task 3: Release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the release workflow**

Create `.github/workflows/release.yml` with exactly this content:

```yaml
name: release

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
      - uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7.6.0
      - run: uv build
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: dist
          path: dist/

  publish-testpypi:
    needs: build
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # v1.14.0
        with:
          repository-url: https://test.pypi.org/legacy/

  publish-pypi:
    needs: build
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # v1.14.0
```

Notes for the implementer: `gh-action-pypi-publish` uploads `dist/` by default, so `publish-pypi` needs no `with:` block. OIDC requires `permissions: id-token: write` on each publish job — it is intentionally absent from `build`, which needs no token.

- [ ] **Step 2: Validate the workflow YAML**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add Trusted-Publishing release workflow"
```

---

## Task 4: Documentation

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Fix the packaging inaccuracy in CONTRIBUTING.md**

In `CONTRIBUTING.md`, find this sentence (around line 49):

```
Steps 2–6 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point, the `[mt5]` extra, the bundled schema file), build and install the wheel before publishing:
```

The schema file is **not** bundled in the wheel (it is regenerated from the model at runtime). Replace that sentence with:

```
Steps 2–6 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point and the `[mt5]` extra), build and install the wheel before publishing:
```

- [ ] **Step 2: Add a Releasing section to CONTRIBUTING.md**

In `CONTRIBUTING.md`, insert a new section immediately before the `## Conventions` section (the last section):

```markdown
## Releasing

Releases publish to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — there is no stored API token. The publish workflow is [`.github/workflows/release.yml`](.github/workflows/release.yml).

**One-time setup (already done for an existing project, required once per index):**

- On PyPI and TestPyPI, register a pending publisher: owner `tanem`, repository `mt5-pnl-exporter`, workflow `release.yml`, environment `pypi` (PyPI) / `testpypi` (TestPyPI).
- On GitHub, create the `pypi` and `testpypi` repository Environments.

**Rehearse to TestPyPI** (validates the OIDC handshake and the rendered page without burning a real version):

1. Actions tab → `release` workflow → Run workflow (`workflow_dispatch`). This builds and uploads to TestPyPI.

**Publish a real release:**

1. Tag the commit, e.g. `git tag v1.0.0`.
2. Draft a GitHub Release against that tag with release notes (the notes are the changelog).
3. Publish the Release. The `release: published` event runs `release.yml`, which builds and uploads to PyPI.

A PyPI version is immutable once uploaded — the version number cannot be reused. The TestPyPI rehearsal de-risks the first upload.
```

- [ ] **Step 3: Add a release note to CLAUDE.md**

In `CLAUDE.md`, find the `## Commands` code block and add this line after the `schema` command line:

```bash
uv run twine check --strict dist/*             # validate built artifacts before release
```

Then, in the `## Gotchas` section, find the Renovate gotcha that begins **"Dependencies are Renovate-managed; don't hand-bump them."** Append this sentence to that bullet (after the existing text):

```
Releases publish to PyPI via Trusted Publishing in `.github/workflows/release.yml` (published GitHub Release → PyPI; `workflow_dispatch` → TestPyPI); see CONTRIBUTING.md's "Releasing" section.
```

- [ ] **Step 4: Verify the docs reference real paths**

Run: `test -f .github/workflows/release.yml && grep -q "Releasing" CONTRIBUTING.md && grep -q "twine check" CLAUDE.md && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md CLAUDE.md
git commit -m "docs: document the release process and correct packaging notes"
```

---

## Final verification (before opening the PR)

- [ ] Run the full local gate to confirm nothing regressed:

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/mt5_pnl_exporter && uv run pytest && rm -rf dist && uv build && uv run twine check --strict dist/*`
Expected: ruff clean, mypy clean, pytest passes at 100% coverage, build succeeds, twine check `PASSED`.

- [ ] Open the PR with `gh pr create` targeting `main`. CI must pass before merge.

---

## Manual setup — user performs (not subagent-executable)

These are web-UI steps the workflow cannot do. Required **once**, before the first TestPyPI/PyPI run (so the rollout below works). Listed here so they are not forgotten.

1. **PyPI** (https://pypi.org → Account → Publishing → Add a pending publisher):
   - PyPI Project Name: `mt5-pnl-exporter`
   - Owner: `tanem`
   - Repository name: `mt5-pnl-exporter`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. **TestPyPI** (https://test.pypi.org, same form):
   - Environment name: `testpypi` (all else identical).
3. **GitHub** (repo Settings → Environments): create environments named `pypi` and `testpypi`.

## Rollout sequence (after the PR merges)

1. Complete the manual setup above.
2. Trigger `release.yml` via `workflow_dispatch` → publishes to TestPyPI. Confirm the run is green and the page renders at `https://test.pypi.org/project/mt5-pnl-exporter/`.
3. Tag `v1.0.0`, draft a GitHub Release with notes, and publish it → publishes to PyPI.
4. Confirm `https://pypi.org/project/mt5-pnl-exporter/` and that `uv tool install "mt5-pnl-exporter[mt5]"` resolves the new release.
