# Phase 1b cycle 6 — Codecov upload, coverage badge, 100% floor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `codecov/codecov-action@v5` into CI, add a coverage badge to the README, bump the local coverage floor from 95% to 100% (closing the four-statement gap in `cli.py`'s `schema` command and the five Protocol-stub partial branches in `sources/base.py`), and update CLAUDE.md to match. Last cycle of Phase 1b — gates the manual `1.0.0` git tag and `uv publish`.

**Architecture:** Five files change. The Codecov upload (`ci.yml`) consumes the `coverage.xml` already produced by `pytest --cov-report=xml`. The README badge sits between `tests` and `PyPI` in the existing badge row. The 100% floor is enforced by `pytest --cov-fail-under=100` in `pyproject.toml`; the four uncovered statements in `cli.py:198-201` (the `schema` command body) close via one new test in `tests/test_cli.py`; the five Protocol-stub partial branches in `sources/base.py:48-52` close via a new `exclude_lines` regex entry (`\.\.\.$`) under `[tool.coverage.report]`. CLAUDE.md's Commands block updates from `≥95%` to `= 100%`.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `pytest-cov`, `typer` (CLI + `CliRunner`), GitHub Actions, `codecov/codecov-action@v5`.

**Reference spec:** [`docs/superpowers/specs/2026-06-05-phase-1b-cycle-6-design.md`](../specs/2026-06-05-phase-1b-cycle-6-design.md)

---

## File map

| Path | Action | Purpose |
| --- | --- | --- |
| `.github/workflows/ci.yml` | modify | Append Codecov upload step after existing `pytest --cov-report=xml` line. |
| `README.md` | modify | Insert coverage badge between `tests` and `PyPI` in the badge row. |
| `pyproject.toml` | modify | Bump `--cov-fail-under` from 95 → 100 and add inline-`...` exclude pattern. |
| `tests/test_cli.py` | modify | Add `test_schema_command_writes_json_schema` to cover the `schema` command body. |
| `CLAUDE.md` | modify | Swap `≥95%` for `= 100%` on the `uv run pytest` line of the Commands block. |

---

## Task 0: Branch setup and prereq verification

**Files:** none (git + shell only)

- [ ] **Step 0.1: Fast-forward local `main` and cut the cycle branch**

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git checkout main
git pull --ff-only
git checkout -b phase-1b-cycle-6   # skip if already on this branch from the spec commit
git log --oneline -3
```

Expected: HEAD is on `phase-1b-cycle-6`. If the branch already exists (the spec was committed on it in `8152a3d`), `git checkout phase-1b-cycle-6` instead.

- [ ] **Step 0.2: Confirm the Codecov token is configured**

```bash
gh secret list --repo tanem/mt5-pnl-exporter
```

Expected output contains a line for `CODECOV_TOKEN`. If absent, stop and add it (`gh secret set CODECOV_TOKEN --repo tanem/mt5-pnl-exporter`) before continuing — without the token the Codecov upload step will fail on CI.

- [ ] **Step 0.3: Measure current coverage (baseline)**

```bash
uv run pytest --cov-report=term 2>&1 | tail -15
```

Expected: tests pass, total coverage reported as ~98% with the floor at 95% (`Required test coverage of 95% reached.`). The missing lines are `cli.py 198-201` and the partial branches `sources/base.py 48->exit, 49->exit, 50->exit, 51->exit, 52->exit`. Write the baseline number down — you'll compare against it after Task 2.

---

## Task 1: Close the `cli.py` gap with a `schema` command test

**Files:**
- Modify: `tests/test_cli.py`

The four uncovered statements in `cli.py:198-201` are the body of the `schema` subcommand, which writes the JSON Schema to disk. The existing `tests/test_cli.py` already has a module-level `runner = CliRunner()` (line 28) and `from mt5_pnl_exporter.cli import app` (line 18) — reuse both.

- [ ] **Step 1.1: Read the `schema` command source to confirm the contract**

```bash
sed -n '190,202p' src/mt5_pnl_exporter/cli.py
```

Expected output shows the `schema` command takes an `--output` / `-o` flag (default `Path("schema/snapshot.schema.json")`), creates parent dirs, and writes `Snapshot.model_json_schema()` plus a trailing newline. The test exercises this end-to-end.

- [ ] **Step 1.2: Add the failing test**

Append to `tests/test_cli.py` (insertion point: end of file — locate it with `wc -l tests/test_cli.py` first; existing tests already use the same `runner` module global, so no fixtures needed):

```python


def test_schema_command_writes_json_schema(tmp_path: Path) -> None:
    """`schema` writes the pydantic-generated JSON Schema to the chosen path."""
    output = tmp_path / "snapshot.schema.json"

    result = runner.invoke(app, ["schema", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    parsed = json.loads(output.read_text())
    assert "$defs" in parsed, "expected the pydantic-generated schema, not stub output"
```

`json`, `Path`, `runner`, and `app` are already imported at the top of the file (lines 10, 12, 18, 28).

- [ ] **Step 1.3: Run the new test on its own and confirm it passes**

```bash
uv run pytest tests/test_cli.py::test_schema_command_writes_json_schema -v
```

Expected: PASS. (The implementation already exists; the test is closing a coverage gap, not driving new behaviour.)

- [ ] **Step 1.4: Confirm the `cli.py:198-201` gap is closed**

```bash
uv run pytest --cov-report=term 2>&1 | grep -E "cli\.py|TOTAL|sources/base\.py"
```

Expected:
- `src/mt5_pnl_exporter/cli.py` now reports `100%` with no missing lines.
- `sources/base.py` still reports `86%` (its five partial branches are closed in Task 2).
- `TOTAL` is now around `99%` — still below 100, by design.

- [ ] **Step 1.5: Commit**

```bash
git add tests/test_cli.py
git commit -m "test(cli): cover the schema command body"
```

---

## Task 2: Close the `sources/base.py` Protocol-stub gap via coverage config

**Files:**
- Modify: `pyproject.toml` (lines 52-57, the `exclude_lines` list)

The five "missing" branches on `sources/base.py:48-52` are the `enter-method → exit` branch on each Protocol method — bodies are literally `...`, and `DataSource` is a Protocol that's implemented but never instantiated. The bodies are uncallable by language design; the right fix is a coverage exclusion, not a test.

- [ ] **Step 2.1: Confirm the `...$`-anchored regex matches only the Protocol stubs**

```bash
grep -rn '\.\.\.$' src/
```

Expected output (and only this output — five lines, all in `sources/base.py`):

```
src/mt5_pnl_exporter/sources/base.py:48:    def account_info(self, login: int) -> AccountInfo: ...
src/mt5_pnl_exporter/sources/base.py:49:    def fetch_closed_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]: ...
src/mt5_pnl_exporter/sources/base.py:50:    def fetch_open_positions(self, login: int) -> list[OpenPosition]: ...
src/mt5_pnl_exporter/sources/base.py:51:    def fetch_cash_flows(self, login: int, date_from: int, date_to: int) -> list[CashFlow]: ...
src/mt5_pnl_exporter/sources/base.py:52:    def shutdown(self) -> None: ...
```

If any other line matches, stop and revisit — the regex would over-exclude. Tighten it before proceeding.

- [ ] **Step 2.2: Add the `\.\.\.$` exclude pattern**

Open `pyproject.toml`. The current `[tool.coverage.report]` block (lines ~49-57) reads:

```toml
[tool.coverage.report]
source = ["src/mt5_pnl_exporter"]
branch = true
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

Add one entry to `exclude_lines` — the last item, with a trailing comment so the intent is clear:

```toml
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "\\.\\.\\.$",   # Protocol method stubs ending in `...`
]
```

The `\\.` double-escapes are because TOML strings interpret backslash. The compiled regex is `\.\.\.$`.

- [ ] **Step 2.3: Verify the gap closes**

```bash
uv run pytest --cov-report=term 2>&1 | grep -E "sources/base\.py|TOTAL"
```

Expected:
- `sources/base.py` now reports `100%` with no partial branches.
- `TOTAL` is now `100%`.
- The line `Required test coverage of 95% reached. Total coverage: 100.00%` (the floor is still 95% — bumping it is Task 3).

- [ ] **Step 2.4: Commit**

```bash
git add pyproject.toml
git commit -m "test(cov): exclude Protocol method stubs from branch coverage"
```

---

## Task 3: Bump the coverage floor to 100%

**Files:**
- Modify: `pyproject.toml:43` (the `[tool.pytest.ini_options] addopts` line)

Now that real coverage is 100%, lock the floor in. The threshold lives in `addopts` so it applies to every `pytest` invocation, including CI.

- [ ] **Step 3.1: Bump the floor**

Open `pyproject.toml`. Line 43 currently reads:

```toml
addopts = "--cov=mt5_pnl_exporter --cov-report=term-missing --cov-fail-under=95"
```

Becomes:

```toml
addopts = "--cov=mt5_pnl_exporter --cov-report=term-missing --cov-fail-under=100"
```

- [ ] **Step 3.2: Verify the floor holds**

```bash
uv run pytest 2>&1 | tail -5
```

Expected: tests pass; the final line reads `Required test coverage of 100% reached. Total coverage: 100.00%`. If coverage dips below 100, stop — something regressed; investigate before continuing.

- [ ] **Step 3.3: Sanity-check the floor actually fails the suite if coverage drops**

This is a one-off confidence check, not committed. Temporarily comment out the new test from Task 1 and re-run:

```bash
# Quick sanity check — DO NOT COMMIT THIS STATE
# In tests/test_cli.py, prefix the new test with @pytest.mark.skip("sanity") or comment out
uv run pytest 2>&1 | tail -5
```

Expected: pytest exits non-zero with a `Coverage failure: total of 99.… is less than fail-under=100` message. **Revert the skip/comment immediately** and confirm the suite goes green again before continuing.

(If you'd rather not perturb the test file, equivalent: temporarily change `--cov-fail-under=100` to `--cov-fail-under=101` and observe the failure, then revert. The point is to confirm the new floor is wired to the right knob.)

- [ ] **Step 3.4: Commit**

```bash
git add pyproject.toml
git commit -m "test(cov): bump coverage floor from 95% to 100%"
```

---

## Task 4: Add the Codecov upload step to CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 4.1: Read the current `ci.yml` to anchor on the existing last step**

```bash
sed -n '20,30p' .github/workflows/ci.yml
```

Expected output shows lines 22-23 as:

```yaml
      - run: uv run pre-commit run --all-files
      - run: uv run pytest --cov-report=xml
```

The new step lands immediately after line 23.

- [ ] **Step 4.2: Append the Codecov upload step**

Append to `.github/workflows/ci.yml` directly after the `uv run pytest --cov-report=xml` line (preserving the 6-space indent so it sits as a step inside the existing `steps:` list):

```yaml
      - uses: codecov/codecov-action@v5
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          slug: tanem/mt5-pnl-exporter
          files: ./coverage.xml
```

- [ ] **Step 4.3: Validate the workflow file parses**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```

Expected: `OK`. If YAML parsing fails (indentation slip is the usual culprit), fix and re-run.

- [ ] **Step 4.4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: upload coverage to Codecov via codecov-action@v5"
```

---

## Task 5: Add the coverage badge to the README

**Files:**
- Modify: `README.md:3-6` (the badge row)

- [ ] **Step 5.1: Insert the coverage badge between `tests` and `PyPI`**

The current badge row (lines 3-6) reads:

```markdown
[![Licence](https://img.shields.io/github/license/tanem/mt5-pnl-exporter)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![tests](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mt5-pnl-exporter)](https://pypi.org/project/mt5-pnl-exporter/)
```

Insert this line between the `tests` line and the `PyPI` line (i.e. after current line 5):

```markdown
[![coverage](https://codecov.io/gh/tanem/mt5-pnl-exporter/branch/main/graph/badge.svg)](https://codecov.io/gh/tanem/mt5-pnl-exporter)
```

Final badge row:

```markdown
[![Licence](https://img.shields.io/github/license/tanem/mt5-pnl-exporter)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![tests](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml)
[![coverage](https://codecov.io/gh/tanem/mt5-pnl-exporter/branch/main/graph/badge.svg)](https://codecov.io/gh/tanem/mt5-pnl-exporter)
[![PyPI](https://img.shields.io/pypi/v/mt5-pnl-exporter)](https://pypi.org/project/mt5-pnl-exporter/)
```

- [ ] **Step 5.2: Run the standing Markdown render check on README**

Per memory entry "Markdown render check" — after non-trivial `.md` edits run `gh api /markdown` in gfm + repo context:

```bash
jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' README.md \
  | gh api -X POST /markdown --input - > /tmp/readme-render.html
wc -l /tmp/readme-render.html
```

Expected: HTML output of a few hundred lines, no error from `gh`. Then open the rendered HTML (or eyeball the first ~30 lines for the badge row):

```bash
sed -n '1,40p' /tmp/readme-render.html
```

Expected: the rendered `<p>` for the badge row contains five `<a>` elements in the right order (Licence → Python → tests → coverage → PyPI), each wrapping an `<img>` tag. Flag any visual-only oddities (badge row wrapping, alignment shifts) for human review.

- [ ] **Step 5.3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add Codecov coverage badge between tests and PyPI"
```

---

## Task 6: Update CLAUDE.md to reflect the 100% floor

**Files:**
- Modify: `CLAUDE.md:14`

- [ ] **Step 6.1: Swap the coverage notation**

Line 14 of CLAUDE.md currently reads:

```
uv run pytest                          # tests (coverage ≥95%; schema staleness check included)
```

Becomes:

```
uv run pytest                          # tests (coverage = 100%; schema staleness check included)
```

`≥95%` → `= 100%`. No other CLAUDE.md edits.

- [ ] **Step 6.2: Confirm no other `95%` mentions linger**

```bash
grep -n "95" CLAUDE.md README.md
```

Expected: zero matches in `CLAUDE.md`. README may have unrelated numbers — verify each remaining match is not coverage-related before moving on.

- [ ] **Step 6.3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): coverage floor is now 100%"
```

---

## Task 7: Full local verification

**Files:** none (verification only)

Run the same gate suite CI runs, locally, against the cumulative cycle 6 changes.

- [ ] **Step 7.1: Ruff (lint + format)**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: both report "All checks passed!" / "X files already formatted". Fix any lint issues before continuing.

- [ ] **Step 7.2: Mypy**

```bash
uv run mypy src/mt5_pnl_exporter
```

Expected: `Success: no issues found in N source files`.

- [ ] **Step 7.3: Pre-commit (gitleaks)**

```bash
uv run pre-commit run --all-files
```

Expected: all hooks pass. Gitleaks should find no leaked secrets.

- [ ] **Step 7.4: Full test suite with coverage at 100% floor**

```bash
uv run pytest
```

Expected: final lines read:

```
Required test coverage of 100% reached. Total coverage: 100.00%
======= 84 passed in N.NNs =======
```

(83 tests pre-cycle + 1 new schema-command test = 84.) If anything fails, stop and diagnose.

- [ ] **Step 7.5: Quick log review before pushing**

```bash
git log --oneline phase-1b-cycle-6 ^main
```

Expected: six task commits plus the spec commit (seven total), in this order (oldest → newest):

1. `docs: Phase 1b cycle 6 design (codecov upload + coverage badge)` — spec
2. `docs(spec): cycle 6 expands to bump coverage floor from 95% to 100%` — spec update
3. `test(cli): cover the schema command body` — Task 1
4. `test(cov): exclude Protocol method stubs from branch coverage` — Task 2
5. `test(cov): bump coverage floor from 95% to 100%` — Task 3
6. `ci: upload coverage to Codecov via codecov-action@v5` — Task 4
7. `docs(readme): add Codecov coverage badge between tests and PyPI` — Task 5
8. `docs(claude): coverage floor is now 100%` — Task 6

If a commit is missing or out of order, fix before pushing.

---

## Task 8: Push branch and open PR

**Files:** none (git + gh)

- [ ] **Step 8.1: Push the branch**

```bash
git push -u origin phase-1b-cycle-6
```

Expected: branch pushed; first CI run kicks off automatically.

- [ ] **Step 8.2: Open the PR (regular, not draft)**

Per the standing preference (memory entry "PRs not draft"), open as ready-for-review:

```bash
gh pr create --repo tanem/mt5-pnl-exporter --title "Phase 1b cycle 6: Codecov upload, coverage badge, 100% floor" --body "$(cat <<'EOF'
## Summary

- Add `codecov/codecov-action@v5` upload step to `ci.yml`, consuming the
  `coverage.xml` already produced by `pytest --cov-report=xml`.
- Add a coverage badge between `tests` and `PyPI` in the README badge row.
- Bump the local coverage floor from 95% to 100%, closing the
  four-statement gap in `cli.py`'s `schema` command (one new test) and
  the five Protocol-stub partial branches in `sources/base.py` (one new
  `exclude_lines` regex in `pyproject.toml`).
- Update CLAUDE.md to reflect the 100% floor.

Last cycle of Phase 1b — once this is on `main`, the manual `1.0.0`
git tag and the first `uv publish` proceed.

Spec: [`docs/superpowers/specs/2026-06-05-phase-1b-cycle-6-design.md`](docs/superpowers/specs/2026-06-05-phase-1b-cycle-6-design.md)

## Test plan

- [ ] CI green (`tests` workflow including the new Codecov step)
- [ ] `uv run pytest` reports `Total coverage: 100.00%`
- [ ] Codecov PR comment appears with diff coverage
- [ ] After merge, the README coverage badge populates within a few
      minutes of the first push-to-main upload
EOF
)"
```

Expected: PR opened, URL printed.

- [ ] **Step 8.3: Watch the first CI run**

```bash
gh pr checks --repo tanem/mt5-pnl-exporter --watch
```

Expected: `tests` workflow goes green, including the new Codecov upload step. If the Codecov step fails, the build still passes (the action is non-fatal on upload error by default) — but investigate before merging. The Codecov PR comment typically appears within a minute of the upload step finishing.

- [ ] **Step 8.4: Confirm the badge populates after merge (post-merge step, not part of the PR)**

After the PR merges to `main` and the main-branch CI run completes:

```bash
curl -sI https://codecov.io/gh/tanem/mt5-pnl-exporter/branch/main/graph/badge.svg | head -5
```

Expected: `200 OK`. Open the README on GitHub and confirm the badge renders a real percentage rather than "unknown".

If the badge stays "unknown" after a successful main-branch upload, the Codecov project may not be linked correctly — check codecov.io's project settings against the `slug: tanem/mt5-pnl-exporter` configured in `ci.yml`.

---

## Post-merge: hand-off to the 1.0.0 release sequence

After cycle 6 is on `main`, the manual tag/publish sequence from cycle 4's
spec proceeds (NOT part of this cycle, NOT part of any subsequent PR):

```bash
cd /Users/tane/Code/mt5-pnl-exporter
git checkout main && git pull --ff-only
git tag -a 1.0.0 -m "1.0.0 — first stable release"
git push --tags
uv build
uv publish   # reads UV_PUBLISH_TOKEN, or prompts
```

The git tag uses the package version (`1.0.0`, three components); the schema version stays at `"1.0"` (major.minor only). After the first publish, the follow-up PR from cycle 4's spec lands (GHA trusted-publish workflow + `pyproject` classifiers/urls/inline license).
