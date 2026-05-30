# Phase 1a — Port `mt5-pnl-exporter` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new `mt5-pnl-exporter` GitHub repo containing only the polling-side code from `mt5-pnl`, plus a generated JSON Schema for `snapshot.json`. Release as 0.x (no schema-version commitment yet — that comes in Phase 1b).

**Architecture:** New repo `mt5-pnl-exporter`. Python package `mt5_pnl_exporter`. CLI command `mt5-pnl-exporter`. Mechanical port from the old `mt5pnl` package: keep `poll`, `set-password`, `sources/`, `snapshot.py`, `secrets.py`, the `deals_to_daily` aggregation, and the poll-side of `config.py`. Drop `pnl`, `accounts`, `render.py`, the query-side config (`QueryConfig`, `account_groups`, `staleness_warn_hours`), and `group_daily` / `summary` / `PeriodRow`. Add `schema/snapshot.schema.json` generated from the pydantic `Snapshot` model, with a pytest check that fails when it drifts.

**Tech Stack:** Python 3.12, `uv` for dependency management, `typer` CLI, `pydantic` v2, `pytest` + `pytest-cov`, `ruff`, `mypy --strict`, `pre-commit` with `gitleaks`, GitHub Actions for CI.

---

## File Structure (in `mt5-pnl-exporter`)

```
mt5-pnl-exporter/
├── .github/workflows/ci.yml          # adapted from mt5-pnl
├── .gitignore                        # carried + adjusted
├── .pre-commit-config.yaml           # carried (gitleaks + ruff)
├── .git-blame-ignore-revs            # carried
├── CLAUDE.md                         # slimmed: exporter-only
├── LICENSE                           # carried
├── README.md                         # rewritten
├── config.example.yaml               # poll-side only (no query: section)
├── docs/superpowers/
│   ├── specs/2026-05-31-repo-split-design.md   # moved from mt5-pnl
│   └── plans/2026-05-31-phase-1a-port-exporter.md  # this file, moved
├── pyproject.toml                    # rewritten with new naming
├── schema/snapshot.schema.json       # generated, committed
├── src/mt5_pnl_exporter/
│   ├── __init__.py
│   ├── aggregate.py                  # only deals_to_daily
│   ├── cli.py                        # poll, set-password, schema
│   ├── config.py                     # no QueryConfig, no query field
│   ├── secrets.py                    # unchanged content, renamed import path
│   ├── snapshot.py                   # unchanged content, renamed import path
│   └── sources/
│       ├── __init__.py
│       ├── base.py
│       ├── fixture.py
│       └── mt5.py
└── tests/
    ├── __init__.py
    ├── fixtures/sample_deals.json    # carried
    ├── test_aggregate.py             # only deals_to_daily tests
    ├── test_cli.py                   # only poll, set-password; + schema tests
    ├── test_config.py                # no QueryConfig / group tests
    ├── test_mt5_source.py            # carried
    ├── test_schema_file.py           # NEW: schema staleness check
    ├── test_secrets.py               # carried
    └── test_snapshot.py              # carried
```

**Dropped wholesale:** `src/mt5pnl/render.py`, `tests/test_render.py`.
**Source for everything ported:** the current `mt5-pnl` repo at `/Users/tane/Code/mt5-pnl`. Path references below use `OLD/` as shorthand for that.

---

## Task 1: Create and scaffold the new repo

**Files:**
- Create: new GitHub repo `tanem/mt5-pnl-exporter`
- Create: `~/Code/mt5-pnl-exporter/` (local clone)
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md` skeleton, `.pre-commit-config.yaml`, `.git-blame-ignore-revs`
- Move: `OLD/docs/superpowers/specs/2026-05-31-repo-split-design.md` → new repo
- Move: `OLD/docs/superpowers/plans/2026-05-31-phase-1a-port-exporter.md` → new repo (this file)

- [ ] **Step 1: Create the GitHub repo**

```bash
gh repo create tanem/mt5-pnl-exporter --private --description "MT5 P&L exporter — polls MT5 deal history, writes snapshot.json"
```

- [ ] **Step 2: Clone alongside the old repo**

```bash
cd ~/Code
gh repo clone tanem/mt5-pnl-exporter
cd mt5-pnl-exporter
```

- [ ] **Step 3: Carry over LICENSE, .gitignore, pre-commit config, blame-ignore**

```bash
cp ~/Code/mt5-pnl/LICENSE .
cp ~/Code/mt5-pnl/.gitignore .
cp ~/Code/mt5-pnl/.pre-commit-config.yaml .
cp ~/Code/mt5-pnl/.git-blame-ignore-revs .
```

- [ ] **Step 4: Write `pyproject.toml` with new naming**

```toml
[project]
name = "mt5-pnl-exporter"
version = "0.1.0"
description = "MT5 P&L exporter — polls deal history on a Windows VPS and writes snapshot.json"
authors = [
    { name = "Tane Morgan", email = "464864+tanem@users.noreply.github.com" }
]
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pydantic>=2",
    "pyyaml>=6",
    "keyring>=25",
]

[project.optional-dependencies]
mt5 = [
    "MetaTrader5>=5.0",
]

[project.scripts]
mt5-pnl-exporter = "mt5_pnl_exporter.cli:app"

[build-system]
requires = ["uv_build>=0.11.12,<0.12.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-cov>=5",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-PyYAML>=6",
    "pre-commit>=4",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=mt5_pnl_exporter --cov-report=term-missing --cov-fail-under=95"

[tool.coverage.run]
source = ["src/mt5_pnl_exporter"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["B011"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
files = ["src/mt5_pnl_exporter"]

[[tool.mypy.overrides]]
module = "MetaTrader5"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "mt5_pnl_exporter.cli"
disallow_untyped_decorators = false
```

- [ ] **Step 5: Write a minimal `README.md`**

```markdown
# mt5-pnl-exporter

Polls MT5 deal history on a Windows VPS and writes `snapshot.json`. Part of the
[mt5-pnl](https://github.com/tanem/mt5-pnl) tool family — see
[`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"
```

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json`.
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain.
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic models.

(Full docs to follow as the port lands.)
```

- [ ] **Step 6: Create directory skeleton**

```bash
mkdir -p src/mt5_pnl_exporter/sources tests/fixtures schema docs/superpowers/specs docs/superpowers/plans .github/workflows
touch src/mt5_pnl_exporter/__init__.py src/mt5_pnl_exporter/sources/__init__.py tests/__init__.py
```

- [ ] **Step 7: Write `src/mt5_pnl_exporter/__init__.py`**

```python
"""mt5-pnl-exporter — polls MT5 deal history, writes snapshot.json."""

__version__ = "0.1.0"
```

- [ ] **Step 8: Move spec and plan from the old repo**

```bash
mv ~/Code/mt5-pnl/docs/superpowers/specs/2026-05-31-repo-split-design.md docs/superpowers/specs/
mv ~/Code/mt5-pnl/docs/superpowers/plans/2026-05-31-phase-1a-port-exporter.md docs/superpowers/plans/
```

Then stage the deletion in the old repo:

```bash
cd ~/Code/mt5-pnl
git rm docs/superpowers/specs/2026-05-31-repo-split-design.md docs/superpowers/plans/2026-05-31-phase-1a-port-exporter.md
git commit -m "chore: move spec and plan into mt5-pnl-exporter"
cd ~/Code/mt5-pnl-exporter
```

- [ ] **Step 9: First commit + initial push**

```bash
git add .
git commit -m "chore: scaffold mt5-pnl-exporter

Initial scaffold: pyproject.toml with new naming (mt5_pnl_exporter package,
mt5-pnl-exporter CLI), pre-commit, LICENSE, README skeleton, and the spec +
Phase 1a plan moved over from mt5-pnl."
git push -u origin main
```

- [ ] **Step 10: Verify `uv sync` works**

```bash
uv sync
```

Expected: succeeds, creates `.venv/`, installs dev deps. Coverage threshold may complain because no tests exist yet — that's fine for this task.

---

## Task 2: Port `secrets.py`

**Files:**
- Copy from: `OLD/src/mt5pnl/secrets.py`
- Create: `src/mt5_pnl_exporter/secrets.py`
- Copy from: `OLD/tests/test_secrets.py`
- Create: `tests/test_secrets.py`

`secrets.py` has no internal imports, so this is a pure copy. Tests need their import path updated.

- [ ] **Step 1: Copy the source unchanged**

```bash
cp ~/Code/mt5-pnl/src/mt5pnl/secrets.py src/mt5_pnl_exporter/secrets.py
```

- [ ] **Step 2: Copy the test, fix imports**

```bash
cp ~/Code/mt5-pnl/tests/test_secrets.py tests/test_secrets.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g' tests/test_secrets.py
```

- [ ] **Step 3: Run the tests**

```bash
uv run pytest tests/test_secrets.py -v
```

Expected: PASS for all secret-management and redact-filter cases.

- [ ] **Step 4: Commit**

```bash
git add src/mt5_pnl_exporter/secrets.py tests/test_secrets.py
git commit -m "feat: port secrets.py (keyring + redact filter)"
```

---

## Task 3: Port `sources/base.py`

**Files:**
- Copy from: `OLD/src/mt5pnl/sources/base.py`
- Create: `src/mt5_pnl_exporter/sources/base.py`

`base.py` has no internal imports. No dedicated test file — covered indirectly via fixture / mt5 tests in later tasks.

- [ ] **Step 1: Copy the source unchanged**

```bash
cp ~/Code/mt5-pnl/src/mt5pnl/sources/base.py src/mt5_pnl_exporter/sources/base.py
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
uv run python -c "from mt5_pnl_exporter.sources.base import Deal, AccountInfo, DataSource, DEAL_TYPE_BALANCE, DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/mt5_pnl_exporter/sources/base.py
git commit -m "feat: port sources/base.py (DataSource protocol + MT5 constants)"
```

---

## Task 4: Port `snapshot.py`

**Files:**
- Copy from: `OLD/src/mt5pnl/snapshot.py`
- Create: `src/mt5_pnl_exporter/snapshot.py`
- Copy from: `OLD/tests/test_snapshot.py`
- Create: `tests/test_snapshot.py`

`snapshot.py` has no internal imports — pure copy. Keep `SCHEMA_VERSION = 1` (integer); the `major.minor` policy ships in Phase 1b, not 1a.

- [ ] **Step 1: Copy the source unchanged**

```bash
cp ~/Code/mt5-pnl/src/mt5pnl/snapshot.py src/mt5_pnl_exporter/snapshot.py
```

- [ ] **Step 2: Copy the test, fix imports**

```bash
cp ~/Code/mt5-pnl/tests/test_snapshot.py tests/test_snapshot.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g' tests/test_snapshot.py
```

- [ ] **Step 3: Run the tests**

```bash
uv run pytest tests/test_snapshot.py -v
```

Expected: PASS for all snapshot read/write/atomicity/version-mismatch cases.

- [ ] **Step 4: Commit**

```bash
git add src/mt5_pnl_exporter/snapshot.py tests/test_snapshot.py
git commit -m "feat: port snapshot.py (atomic JSON read/write, version check)"
```

---

## Task 5: Port `sources/fixture.py` (+ fixture data)

**Files:**
- Copy from: `OLD/tests/fixtures/sample_deals.json`
- Create: `tests/fixtures/sample_deals.json`
- Copy from: `OLD/src/mt5pnl/sources/fixture.py`
- Create: `src/mt5_pnl_exporter/sources/fixture.py`

The fixture path in the old `fixture.py` is computed via `Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "sample_deals.json"`. Same number of `parent` calls in the new layout — no change needed.

- [ ] **Step 1: Copy the fixture data**

```bash
cp ~/Code/mt5-pnl/tests/fixtures/sample_deals.json tests/fixtures/sample_deals.json
```

- [ ] **Step 2: Copy the source, fix imports**

```bash
cp ~/Code/mt5-pnl/src/mt5pnl/sources/fixture.py src/mt5_pnl_exporter/sources/fixture.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g' src/mt5_pnl_exporter/sources/fixture.py
```

- [ ] **Step 3: Smoke-test it loads**

```bash
uv run python -c "from mt5_pnl_exporter.sources.fixture import FixtureSource; src = FixtureSource(); print(len(src.fetch_deals(1234567, 0, 9999999999)), 'deals for 1234567')"
```

Expected: a non-zero deal count.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/sample_deals.json src/mt5_pnl_exporter/sources/fixture.py
git commit -m "feat: port sources/fixture.py + sample_deals.json"
```

---

## Task 6: Port `sources/mt5.py`

**Files:**
- Copy from: `OLD/src/mt5pnl/sources/mt5.py`
- Create: `src/mt5_pnl_exporter/sources/mt5.py`
- Copy from: `OLD/tests/test_mt5_source.py`
- Create: `tests/test_mt5_source.py`

- [ ] **Step 1: Copy the source, fix imports**

```bash
cp ~/Code/mt5-pnl/src/mt5pnl/sources/mt5.py src/mt5_pnl_exporter/sources/mt5.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g' src/mt5_pnl_exporter/sources/mt5.py
```

- [ ] **Step 2: Copy the tests, fix imports**

```bash
cp ~/Code/mt5-pnl/tests/test_mt5_source.py tests/test_mt5_source.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g; s/"mt5pnl\./"mt5_pnl_exporter./g' tests/test_mt5_source.py
```

The third `sed` pattern is for `monkeypatch.setattr("mt5pnl.sources.mt5...", ...)`-style string literals — verify by grepping after:

```bash
grep -n 'mt5pnl' tests/test_mt5_source.py || echo "no residual mt5pnl references"
```

Expected: `no residual mt5pnl references`. If any remain, fix them by hand.

- [ ] **Step 3: Run the tests**

```bash
uv run pytest tests/test_mt5_source.py -v
```

Expected: all mt5-source tests PASS (these mock the `MetaTrader5` module, so they run on macOS).

- [ ] **Step 4: Commit**

```bash
git add src/mt5_pnl_exporter/sources/mt5.py tests/test_mt5_source.py
git commit -m "feat: port sources/mt5.py (live MT5 data source)"
```

---

## Task 7: Port `aggregate.py` (slimmed to `deals_to_daily` only)

**Files:**
- Create: `src/mt5_pnl_exporter/aggregate.py` (subset of `OLD/src/mt5pnl/aggregate.py`)
- Create: `tests/test_aggregate.py` (subset of `OLD/tests/test_aggregate.py`)

Drop `PeriodRow`, `_week_start`, `_month_start`, `group_daily`, `summary`. Keep `deals_to_daily` and its imports.

- [ ] **Step 1: Write the slimmed `aggregate.py`**

```python
"""Aggregation: closing deals → per-account-per-day buckets."""

from __future__ import annotations

import datetime
from typing import Any

from mt5_pnl_exporter.snapshot import DailyRow
from mt5_pnl_exporter.sources.base import (
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BALANCE,
    Deal,
)


def deals_to_daily(deals: list[Deal]) -> list[DailyRow]:
    """Aggregate closing deals into per-account per-day buckets."""
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for d in deals:
        # MT5Source pre-filters; FixtureSource does not — this filter handles both
        if d.type == DEAL_TYPE_BALANCE:
            continue
        if d.entry not in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT):
            continue
        date = datetime.datetime.fromtimestamp(d.time, tz=datetime.UTC).strftime("%Y-%m-%d")
        key = (d.account, date)
        if key not in buckets:
            buckets[key] = {
                "account": d.account,
                "date": date,
                "pnl": 0.0,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            }
        net = d.profit + d.swap + d.commission + d.fee
        b = buckets[key]
        b["pnl"] = round(b["pnl"] + net, 2)
        b["trades"] += 1
        if net >= 0:
            b["wins"] += 1
            b["gross_profit"] = round(b["gross_profit"] + net, 2)
        else:
            b["losses"] += 1
            b["gross_loss"] = round(b["gross_loss"] + net, 2)
    return [
        DailyRow(**v) for v in sorted(buckets.values(), key=lambda r: (r["account"], r["date"]))
    ]
```

Save as `src/mt5_pnl_exporter/aggregate.py`.

- [ ] **Step 2: Port the relevant tests**

Read `OLD/tests/test_aggregate.py`. Identify which tests target `deals_to_daily` (look for `deals_to_daily(` in the body); drop tests that target `group_daily` / `summary` / `PeriodRow`. Write the kept tests to `tests/test_aggregate.py` with imports rewritten:

```bash
cp ~/Code/mt5-pnl/tests/test_aggregate.py tests/test_aggregate.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g' tests/test_aggregate.py
```

Then open `tests/test_aggregate.py` and delete any test functions that reference `group_daily`, `summary`, or `PeriodRow`. Delete unused imports afterwards.

- [ ] **Step 3: Run the tests**

```bash
uv run pytest tests/test_aggregate.py -v
```

Expected: PASS for all `deals_to_daily` cases. Coverage of `aggregate.py` should be ≥95%.

- [ ] **Step 4: Commit**

```bash
git add src/mt5_pnl_exporter/aggregate.py tests/test_aggregate.py
git commit -m "feat: port aggregate.py (deals_to_daily only)

Drop PeriodRow, group_daily, summary — those belong in the Go CLI per the
repo-split design."
```

---

## Task 8: Port `config.py` (slimmed — no QueryConfig, no query field)

**Files:**
- Create: `src/mt5_pnl_exporter/config.py` (subset of `OLD/src/mt5pnl/config.py`)
- Create: `tests/test_config.py` (subset of `OLD/tests/test_config.py`)
- Create: `config.example.yaml` (no `query:` section)

Drop `QueryConfig` entirely. Drop the `query` field from `Config`. Drop `_validate_groups` (it referenced `self.query.account_groups`). Keep account-label uniqueness as its own validator.

- [ ] **Step 1: Write the slimmed `config.py`**

```python
"""Config loading: pydantic models, keyring-first secret resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator

from mt5_pnl_exporter.secrets import get_investor_password, redact_filter

_DEFAULT_CONFIG_PATH = Path("config.yaml")


class AccountConfig(BaseModel):
    label: str
    login: int
    server: str


class PollConfig(BaseModel):
    terminal_path: str = ""

    @field_validator("terminal_path", mode="before")
    @classmethod
    def _terminal_path_none_to_empty(cls, v: Any) -> str:
        return v or ""


class Config(BaseModel):
    snapshot_path: str
    accounts: list[AccountConfig]
    poll: PollConfig = PollConfig()

    @field_validator("accounts")
    @classmethod
    def accounts_not_empty(cls, v: list[AccountConfig]) -> list[AccountConfig]:
        if not v:
            raise ValueError("accounts list must not be empty")
        return v

    @model_validator(mode="after")
    def _labels_unique(self) -> Config:
        labels = [a.label for a in self.accounts]
        if len(set(labels)) != len(labels):
            raise ValueError("account labels must be unique")
        return self


def check_file_perms(path: Path) -> None:
    """Warn if config has group/other-readable bits.

    Only call from poll — query commands skip this.
    """
    # Windows reports synthesised POSIX bits (typically 0o666) — file security
    # is handled by NTFS ACLs there, not mode bits.
    if os.name == "nt":
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        from rich.console import Console

        Console(stderr=True).print(
            f"[yellow]Warning: {path} has permissions {oct(mode)} — should be 600. "
            "Run: chmod 600 config.yaml[/yellow]"
        )


def load_config(config_path: Path | None = None) -> Config:
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and fill in your values."
        )
    with path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return Config.model_validate(raw)


def resolve_passwords(cfg: Config) -> dict[int, str]:
    """Return {login: investor_password} from keyring; raise if any missing."""
    passwords: dict[int, str] = {}
    missing: list[str] = []
    for acct in cfg.accounts:
        pw = get_investor_password(acct.login)
        if not pw:
            missing.append(f"{acct.label} (login {acct.login})")
        else:
            redact_filter.register(pw)
            passwords[acct.login] = pw
    if missing:
        raise RuntimeError(
            "Investor password not found in keyring for: "
            + ", ".join(missing)
            + "\nRun: mt5-pnl-exporter set-password <login>"
        )
    return passwords
```

Save as `src/mt5_pnl_exporter/config.py`.

- [ ] **Step 2: Port the relevant tests**

```bash
cp ~/Code/mt5-pnl/tests/test_config.py tests/test_config.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g' tests/test_config.py
```

Then open `tests/test_config.py` and delete any test functions that reference `QueryConfig`, `account_groups`, `staleness_warn_hours`, or `query:` YAML sections. Delete unused imports afterwards.

- [ ] **Step 3: Write `config.example.yaml`**

```yaml
# mt5-pnl-exporter config — poll-side only.
snapshot_path: /var/data/mt5-pnl/snapshot.json

poll:
  terminal_path: 'C:\Program Files\MetaTrader 5\terminal64.exe'

accounts:
  - label: Trend EA
    login: 1234567
    server: BrokerName-Real
  - label: Scalper EA
    login: 7654321
    server: BrokerName-Real
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS for all poll-side / account-label tests. Coverage of `config.py` ≥95%.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/config.py tests/test_config.py config.example.yaml
git commit -m "feat: port config.py (drop query-side: QueryConfig, account_groups)

Drop QueryConfig, the query field on Config, and the account_groups
validator. Those belong in the Go CLI per the repo-split design."
```

---

## Task 9: Port `cli.py` (slimmed — `poll`, `set-password`, `schema` only)

**Files:**
- Create: `src/mt5_pnl_exporter/cli.py` (subset of `OLD/src/mt5pnl/cli.py` + new `schema` command)
- Create: `tests/test_cli.py` (subset of `OLD/tests/test_cli.py` + new `schema` tests)

Drop `pnl`, `accounts`, the `_parse_last`, `_resolve_group`, `_staleness_warn`, `_build_fixture_snapshot` helpers. Add `schema` command.

- [ ] **Step 1: Write the slimmed `cli.py` with the new `schema` command**

```python
"""mt5-pnl-exporter CLI — poll | set-password | schema"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mt5_pnl_exporter import aggregate, snapshot
from mt5_pnl_exporter.config import check_file_perms, load_config, resolve_passwords
from mt5_pnl_exporter.secrets import redact_filter, set_investor_password
from mt5_pnl_exporter.snapshot import AccountSnapshot, Snapshot
from mt5_pnl_exporter.sources.base import DataSource

app = typer.Typer(help="MT5 P&L exporter — poll deal history, write snapshot.json.", add_completion=False)
err = Console(stderr=True)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(redact_filter)
    logging.basicConfig(level=level, handlers=[handler], format="[%(levelname)s] %(message)s")


@app.command()
def poll(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    source: Annotated[str, typer.Option(help="Data source: mt5 or fixture")] = "mt5",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Fetch deal history from MT5 and write snapshot.json. Run on the VPS."""
    _setup_logging(verbose)
    log = logging.getLogger(__name__)

    check_file_perms(config_path or Path("config.yaml"))
    cfg = load_config(config_path)
    snap_path = Path(cfg.snapshot_path)
    snap_path.parent.mkdir(parents=True, exist_ok=True)

    src: DataSource
    if source == "fixture":
        from mt5_pnl_exporter.sources.fixture import FixtureSource

        src = FixtureSource()
        passwords: dict[int, str] = {}
    else:
        from mt5_pnl_exporter.sources.mt5 import MT5Source

        passwords = resolve_passwords(cfg)
        servers = {a.login: a.server for a in cfg.accounts}
        src = MT5Source(cfg.poll.terminal_path, passwords, servers)

    now = datetime.datetime.now(tz=datetime.UTC)
    epoch_from = 0
    epoch_to = int(now.timestamp())

    prior_by_login: dict[int, AccountSnapshot] = {}
    try:
        prior = snapshot.read(snap_path)
        prior_by_login = {a.login: a for a in prior.accounts}
    except FileNotFoundError:
        pass

    accounts_out: list[AccountSnapshot] = []
    daily_out = []
    error_count = 0

    for acct in cfg.accounts:
        try:
            info = src.account_info(acct.login)
            deals = src.fetch_deals(acct.login, epoch_from, epoch_to)
            daily = aggregate.deals_to_daily(deals)
            daily_out.extend(daily)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=info.currency,
                    balance=info.balance,
                    equity=info.equity,
                    last_success=now.isoformat().replace("+00:00", "Z"),
                    last_error=None,
                )
            )
            trade_count = sum(r.trades for r in daily)
            day_count = len(daily)
            log.info(
                f"[poll] {acct.label} ({acct.login}): {trade_count} trades -> {day_count} days  OK"
            )
        except Exception as exc:
            error_count += 1
            log.error(f"[poll] {acct.label} ({acct.login}): FAILED — {exc}")
            prior_acct = prior_by_login.get(acct.login)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=prior_acct.currency if prior_acct else "",
                    balance=prior_acct.balance if prior_acct else 0.0,
                    equity=prior_acct.equity if prior_acct else 0.0,
                    last_success=prior_acct.last_success if prior_acct else None,
                    last_error=str(exc),
                )
            )

    try:
        if error_count == len(cfg.accounts) and prior_by_login:
            log.error(
                f"[poll] All {error_count} accounts failed; "
                f"keeping previous snapshot at {snap_path}."
            )
            raise SystemExit(1)

        snap = Snapshot(
            schema_version=1,
            generated_at=now.isoformat().replace("+00:00", "Z"),
            accounts=accounts_out,
            daily=daily_out,
            cash_flows=[],
        )
        snapshot.write(snap_path, snap)
        log.info(f"[poll] wrote {snap_path}  ({now.strftime('%Y-%m-%d %H:%M')})")
    finally:
        if hasattr(src, "shutdown"):
            src.shutdown()

    if error_count:
        raise SystemExit(1)


@app.command("set-password")
def set_password(
    login: Annotated[int, typer.Argument(help="MT5 account login number")],
) -> None:
    """Store an investor password in the OS keychain (never echoed to terminal)."""
    import getpass

    pw = getpass.getpass(f"Investor password for login {login}: ")
    if not pw:
        err.print("[red]Password cannot be empty.[/red]")
        raise SystemExit(1)
    set_investor_password(login, pw)
    err.print(f"[green]Password stored in keychain for login {login}.[/green]")


@app.command()
def schema(
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the JSON Schema file.")
    ] = Path("schema/snapshot.schema.json"),
) -> None:
    """Regenerate the JSON Schema for snapshot.json from the pydantic models."""
    schema_dict = Snapshot.model_json_schema()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema_dict, indent=2) + "\n")
    err.print(f"[green]Wrote {output}[/green]")
```

Save as `src/mt5_pnl_exporter/cli.py`.

- [ ] **Step 2: Port the relevant tests**

```bash
cp ~/Code/mt5-pnl/tests/test_cli.py tests/test_cli.py
sed -i '' 's/from mt5pnl\./from mt5_pnl_exporter./g; s/import mt5pnl\./import mt5_pnl_exporter./g; s/"mt5pnl\./"mt5_pnl_exporter./g' tests/test_cli.py
```

Then open `tests/test_cli.py` and:
- Delete test functions that exercise `pnl`, `accounts`, `_parse_last`, `_resolve_group`, `_staleness_warn`, `_build_fixture_snapshot`, or anything that references `render.*`.
- Verify the remaining tests cover `poll`, `set-password` only.
- Delete unused imports afterwards.

- [ ] **Step 3: Verify no residual references**

```bash
grep -n 'mt5pnl' tests/test_cli.py src/mt5_pnl_exporter/cli.py || echo "no residual mt5pnl references"
grep -nE '\b(pnl|accounts)\b' src/mt5_pnl_exporter/cli.py
```

Expected: `no residual mt5pnl references`. The second grep should find no `pnl` / `accounts` command definitions in the new `cli.py`.

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: PASS for all `poll` and `set-password` cases.

- [ ] **Step 5: Commit**

```bash
git add src/mt5_pnl_exporter/cli.py tests/test_cli.py
git commit -m "feat: port cli.py (poll + set-password + new schema command)

Drop pnl, accounts, and their helpers — those belong in the Go CLI. Add a
schema command that writes schema/snapshot.schema.json from the pydantic
models."
```

---

## Task 10: Generate `schema/snapshot.schema.json` and add a staleness check

**Files:**
- Create: `schema/snapshot.schema.json` (generated)
- Create: `tests/test_schema_file.py`

The pytest check is the staleness guard: if a model changes without regenerating the schema file, this test fails.

- [ ] **Step 1: Generate the schema file**

```bash
uv run mt5-pnl-exporter schema
```

Expected: writes `schema/snapshot.schema.json`. Open it and confirm it contains the `Snapshot`, `AccountSnapshot`, `DailyRow` definitions.

- [ ] **Step 2: Write the staleness test**

```python
"""Schema file staleness check — fails if the committed file drifts from the models."""

from __future__ import annotations

import json
from pathlib import Path

from mt5_pnl_exporter.snapshot import Snapshot

_SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "snapshot.schema.json"


def test_schema_file_matches_models() -> None:
    expected = json.dumps(Snapshot.model_json_schema(), indent=2) + "\n"
    actual = _SCHEMA_PATH.read_text()
    assert actual == expected, (
        "schema/snapshot.schema.json is out of date. "
        "Run: uv run mt5-pnl-exporter schema"
    )
```

Save as `tests/test_schema_file.py`.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/test_schema_file.py -v
```

Expected: PASS.

- [ ] **Step 4: Run the full test suite to confirm coverage**

```bash
uv run pytest
```

Expected: all tests PASS, coverage ≥95%.

- [ ] **Step 5: Commit**

```bash
git add schema/snapshot.schema.json tests/test_schema_file.py
git commit -m "feat: publish schema/snapshot.schema.json + staleness check

Generated from the pydantic Snapshot model. The pytest staleness check
fails CI if a model change isn't accompanied by a schema regeneration."
```

---

## Task 11: Lint, type-check, and pre-commit pass

**Files:**
- Verify: `pyproject.toml` (ruff/mypy config), `.pre-commit-config.yaml`

- [ ] **Step 1: Ruff lint**

```bash
uv run ruff check src/ tests/
```

Expected: no errors. Fix any imports left dangling by the slimming work.

- [ ] **Step 2: Ruff format check**

```bash
uv run ruff format --check src/ tests/
```

Expected: no formatting deltas. If any, run `uv run ruff format src/ tests/` and recommit.

- [ ] **Step 3: Mypy strict**

```bash
uv run mypy src/mt5_pnl_exporter
```

Expected: `Success`. Fix any strict-mode complaints introduced by the port.

- [ ] **Step 4: Install + run pre-commit**

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Expected: gitleaks + any other hooks PASS.

- [ ] **Step 5: Commit any fix-ups (if needed)**

```bash
git add -p
git commit -m "chore: ruff/mypy fix-ups from port"
```

If nothing needs fixing, skip this commit.

---

## Task 12: Port and adapt GitHub Actions CI

**Files:**
- Copy from: `OLD/.github/workflows/*.yml`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Copy the workflow and rename package paths**

```bash
cp ~/Code/mt5-pnl/.github/workflows/*.yml .github/workflows/
sed -i '' 's/mt5pnl/mt5_pnl_exporter/g; s|src/mt5pnl|src/mt5_pnl_exporter|g' .github/workflows/*.yml
```

- [ ] **Step 2: Verify the workflow file makes sense**

Read `.github/workflows/ci.yml`. Confirm it: installs uv, syncs deps, runs ruff, runs mypy, runs pytest (which now includes `test_schema_file.py`, so schema staleness is enforced).

- [ ] **Step 3: Commit and push, watch CI**

```bash
git add .github/workflows/
git commit -m "ci: port GitHub Actions workflow (lint, mypy, pytest, schema check)"
git push
```

Then:

```bash
gh run watch
```

Expected: workflow PASSes on the first run.

- [ ] **Step 4: Fix any CI breakage**

If anything fails on CI but worked locally, investigate (path differences, missing dev dep, etc.), fix, recommit, repush. Iterate until green.

---

## Task 13: Write `CLAUDE.md` for the new repo

**Files:**
- Create: `CLAUDE.md`

The old `CLAUDE.md` is a mix of exporter + query info. Write a fresh one scoped to exporter.

- [ ] **Step 1: Write `CLAUDE.md`**

```markdown
# CLAUDE.md

MT5 P&L exporter: a `uv`-managed Python 3.12 CLI (`mt5-pnl-exporter`) that polls
MT5 deal history on a Windows VPS and writes `snapshot.json`. The schema lives
in `schema/snapshot.schema.json`; consumers (CLI, UI) read the snapshot against
the schema. See [`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract.

## Commands

```bash
uv sync                                # install dev deps
uv sync --extra mt5                    # VPS: also install MetaTrader5
uv run pytest                          # tests (coverage ≥95%; schema staleness check included)
uv run mt5-pnl-exporter poll --source fixture   # smoke-test without creds
uv run mt5-pnl-exporter schema         # regenerate schema/snapshot.schema.json
uv run ruff check src/ tests/
uv run mypy src/mt5_pnl_exporter
uv run pre-commit install              # gitleaks secret-scan hook
```

## Architecture

- `cli.py` — Typer app; commands: `poll`, `set-password`, `schema`.
- `sources/` — `DataSource` protocol (`base.py`); `MT5Source` (live, Windows only); `FixtureSource` (local JSON for dev / tests).
- `aggregate.py` — `deals_to_daily()` runs inside `poll`.
- `snapshot.py` — typed pydantic models + atomic `write` (temp file + `replace`). `read()` rejects mismatched `SCHEMA_VERSION`.
- `config.py` — pydantic models + YAML loader. Poll-side only — no query-side config (`account_groups`, `staleness_warn_hours`) here.
- `secrets.py` — keyring access and log redaction.
- `schema/snapshot.schema.json` — generated from the pydantic `Snapshot` model. `tests/test_schema_file.py` fails CI if it drifts.

## Gotchas

- **Never import `MetaTrader5` at module level.** It is deferred inside `MT5Source` (sources/mt5.py).
- **Investor passwords only**, stored in the VPS keychain via `keyring`. `redact_filter` (secrets.py) strips them from logs. The `config.yaml` perms check (`check_file_perms`) is enforced by `poll` only.
- **A dedicated MT5 terminal is required**: `mt5.login()` switches the terminal's active account, so pointing it at an EA terminal logs the EA out.
- **MT5 history sync is async.** `fetch_deals()` waits for `history_deals_total(from, to)` to stabilise before calling `history_deals_get()`.
- **Deal filtering**: only `DEAL_ENTRY_OUT`/`INOUT` closing deals count; `DEAL_TYPE_BALANCE` is excluded. Net P&L = profit+swap+commission+fee; net of exactly 0 counts as a win.
- **Regenerate the schema after model changes**: `uv run mt5-pnl-exporter schema`. `tests/test_schema_file.py` catches missed regenerations.
- **`SCHEMA_VERSION` is still a plain integer** in 0.x. Major.minor versioning ships in Phase 1b.

## Conventions

- NZ English in comments and docs (realise, behaviour, colour). No hyperbole.
- Python 3.12+; `from __future__ import annotations` in every module.
- Tests target `aggregate.py` and `snapshot.py`. Use `FixtureSource` instead of mocking MT5.
- After changing commands, architecture, or a gotcha above, update this file and README.md in the same change.
```

Save as `CLAUDE.md`.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: write CLAUDE.md scoped to the exporter"
```

---

## Task 14: Flesh out README.md

**Files:**
- Modify: `README.md` (replace the skeleton from Task 1)

- [ ] **Step 1: Write the full README**

```markdown
# mt5-pnl-exporter

Polls MT5 deal history on a Windows VPS and writes `snapshot.json` — the
published contract that downstream tools (CLI, UI) consume.

Part of the mt5-pnl tool family. See
[`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract and the wider design.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # VPS, includes MetaTrader5
uv tool install mt5-pnl-exporter          # any OS, schema/smoke-test work
```

## Quick start (VPS)

```bash
mt5-pnl-exporter set-password 1234567        # store investor pw in keychain
cp config.example.yaml config.yaml           # then chmod 600 config.yaml
mt5-pnl-exporter poll                        # writes snapshot.json
```

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json` atomically.
- `mt5-pnl-exporter poll --source fixture` — write a snapshot from `tests/fixtures/sample_deals.json` (smoke test, no creds).
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain (`keyring`).
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic `Snapshot` model.

## Schema

`schema/snapshot.schema.json` is generated from the pydantic models and
committed. CI (`tests/test_schema_file.py`) fails if it drifts. Consumers
vendor the file from a specific release.

Schema version stamping is a plain integer (`SCHEMA_VERSION = 1`) in 0.x.
`major.minor` versioning ships in the 1.0 release (Phase 1b of the repo split).

## Status

0.x — pre-release. Schema may still change. Tag `1.0` ships in Phase 1b once
the planned simplifications have landed.
```

Save as `README.md`.

- [ ] **Step 2: Render-check the README via GitHub's API**

```bash
jq -Rs '{text: ., mode: "gfm", context: "tanem/mt5-pnl-exporter"}' < README.md \
  | gh api -X POST /markdown --input - > /tmp/readme.html
wc -l /tmp/readme.html
```

Expected: non-zero line count, no errors from `gh`. Open `/tmp/readme.html` in a browser if you want to eyeball it.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: flesh out README with install, quick-start, schema notes"
```

---

## Task 15: Verify build for PyPI (no publish yet)

**Files:**
- Build artefacts in `dist/`

- [ ] **Step 1: Build wheel and sdist**

```bash
uv build
ls dist/
```

Expected: `dist/mt5_pnl_exporter-0.1.0-py3-none-any.whl` and `dist/mt5_pnl_exporter-0.1.0.tar.gz` (or similar — `uv build` may emit different artefact names; the point is both wheel and sdist exist).

- [ ] **Step 2: Install the built wheel into a throwaway venv and run the CLI**

```bash
uv venv /tmp/exporter-smoke
source /tmp/exporter-smoke/bin/activate
uv pip install dist/mt5_pnl_exporter-*.whl
mt5-pnl-exporter --help
deactivate
rm -rf /tmp/exporter-smoke
```

Expected: the `--help` output lists `poll`, `set-password`, `schema`.

- [ ] **Step 3: Commit nothing (artefacts are gitignored), proceed**

No commit — `dist/` should already be in `.gitignore`. If not, add it now and commit.

---

## Task 16: End-to-end smoke test against the fixture source

- [ ] **Step 1: Write a temporary config.yaml pointing at a temp snapshot path**

```bash
cat > /tmp/smoke-config.yaml <<'EOF'
snapshot_path: /tmp/smoke-snapshot.json
poll:
  terminal_path: ''
accounts:
  - label: Trend EA
    login: 1234567
    server: BrokerName-Real
  - label: Scalper EA
    login: 7654321
    server: BrokerName-Real
EOF
chmod 600 /tmp/smoke-config.yaml
```

- [ ] **Step 2: Run a fixture poll**

```bash
uv run mt5-pnl-exporter poll --config /tmp/smoke-config.yaml --source fixture
```

Expected: writes `/tmp/smoke-snapshot.json`. The log should show `OK` for both accounts.

- [ ] **Step 3: Verify the snapshot validates against the schema**

```bash
uv run python -c "
import json
from pathlib import Path
from mt5_pnl_exporter.snapshot import read
snap = read(Path('/tmp/smoke-snapshot.json'))
print(f'schema_version={snap.schema_version} accounts={len(snap.accounts)} daily_rows={len(snap.daily)}')
"
```

Expected: `schema_version=1 accounts=2 daily_rows=<some positive number>`.

- [ ] **Step 4: Clean up**

```bash
rm /tmp/smoke-config.yaml /tmp/smoke-snapshot.json
```

---

## Task 17: Tag and push the 0.1.0 release

- [ ] **Step 1: Verify the repo is clean and on `main`**

```bash
git status && git branch --show-current
```

Expected: clean working tree, branch `main`.

- [ ] **Step 2: Tag**

```bash
git tag -a v0.1.0 -m "v0.1.0 — initial port from mt5-pnl

Polling-side code only. Schema generated and committed. Pre-release: schema
may still change before 1.0 (Phase 1b)."
```

- [ ] **Step 3: Push tag**

```bash
git push origin v0.1.0
```

- [ ] **Step 4: Verify the tag on GitHub**

```bash
gh release view v0.1.0 2>/dev/null || gh api repos/tanem/mt5-pnl-exporter/git/refs/tags/v0.1.0
```

Expected: the tag exists on the remote. PyPI publication is intentionally deferred to Phase 1b.

---

## Verification

End-to-end checks that everything works:

- `uv sync` — succeeds with no missing deps.
- `uv run pytest` — all tests pass, coverage ≥95%, schema staleness check is green.
- `uv run ruff check src/ tests/` — no findings.
- `uv run ruff format --check src/ tests/` — no formatting deltas.
- `uv run mypy src/mt5_pnl_exporter` — `Success`.
- `uv run pre-commit run --all-files` — green.
- `uv run mt5-pnl-exporter poll --source fixture` — writes a valid snapshot.
- `uv run mt5-pnl-exporter schema` — regenerates the schema file without diff.
- GitHub Actions CI — green on `main`.
- Tag `v0.1.0` exists on origin.

Done when all of the above are true.
