# Renovate dependency automation + SHA-pinning — design

Date: 2026-06-06

## Goal

Eliminate manual dependency version-chasing — the kind that produced the
2026-06-06 Node 20 deprecation sweep across four GitHub Actions — while adding
supply-chain tamper resistance. The auto-updater pays the maintenance cost of
SHA-pinning rather than a human.

Two motivations, weighted equally:

- **Reduce upkeep.** No more hand-bumping action and dependency versions.
- **Supply-chain security.** Pin actions to immutable commit SHAs so a
  compromised mutable tag cannot inject malicious code, and refresh the lockfile
  so transitive security patches land.

## Background / current state

- One workflow: `.github/workflows/ci.yml` (`tests`).
- Four third-party actions, all pinned to mutable major-version tags:
  `actions/checkout@v6`, `actions/setup-python@v6`, `astral-sh/setup-uv@v7`,
  `codecov/codecov-action@v6`.
- No `dependabot.yml`, no `renovate.json`.
- Strong CI gate on every PR: `ruff check`, `ruff format --check`, `mypy`,
  `pre-commit run --all-files` (gitleaks), `pytest` at **100% coverage**, plus a
  schema-staleness check (`tests/test_schema_file.py`). This gate is what makes
  auto-merge safe — a breaking update fails CI and never reaches auto-merge.
- Publishing is **manual**: a hand-cut git tag (`1.0.0`) after cycle 6. No
  publish workflow exists. Merges to `main` therefore never publish, so
  auto-merging Renovate PRs cannot trigger a release. This stays true if a
  tag-triggered publish workflow is added later, because Renovate merges commits
  but never pushes version tags.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Updater | **Renovate** (over Dependabot) | More configurable grouping, scheduling, auto-merge rules; can self-pin action digests via a preset. |
| Pinning | **Renovate pins**, not hand-pinned | `helpers:pinGitHubActionDigests` opens the pinning PR and keeps SHAs current with version comments — the whole point of pairing pinning with an updater. |
| Scope | **GitHub Actions + Python deps** (`pyproject.toml`, `uv.lock`) | The strong CI gate makes broad scope low-risk; excluding Python deps would recreate the manual-chasing problem. |
| Auto-merge | **digest + minor/patch auto-merge; majors open a PR** | Minor/patch and digests are validated by CI; majors are behaviour-sensitive and deserve human review. |
| Lockfile | **`lockFileMaintenance` enabled** | Periodic `uv.lock` refresh is how transitive security patches land — the security half of the goal. |
| Docs | **CONTRIBUTING.md + SECURITY.md + CLAUDE.md**; not README | CONTRIBUTING is the update-flow home; SECURITY records the supply-chain controls; CLAUDE.md stops future agent sessions fighting the bot. README is user-facing and stays out. |

## Detailed design

### 1. `renovate.json` (repo root)

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "helpers:pinGitHubActionDigests"
  ],
  "lockFileMaintenance": { "enabled": true },
  "packageRules": [
    {
      "description": "Auto-merge digest, minor and patch updates once CI passes",
      "matchUpdateTypes": ["digest", "minor", "patch"],
      "automerge": true
    },
    {
      "description": "Major updates always open a PR for review",
      "matchUpdateTypes": ["major"],
      "automerge": false
    },
    {
      "description": "MetaTrader5 is a Windows-only optional extra CI cannot validate; always review",
      "matchPackageNames": ["MetaTrader5"],
      "automerge": false
    }
  ]
}
```

Behaviour:

- `helpers:pinGitHubActionDigests` pins all four actions from tags to commit
  SHAs with a trailing version comment (e.g. `uses: actions/checkout@<sha> # v6`)
  and keeps the SHA + comment current thereafter.
- `config:recommended` enables Python dependency management
  (`pyproject.toml` / `uv.lock`) and GitHub Actions out of the box.
- Auto-merge uses GitHub's native auto-merge, gated on the `tests` workflow.

Rule precedence note: `packageRules` apply in order, later overriding earlier.
The `MetaTrader5` rule appears after the update-type rules so its
`automerge: false` wins for any `MetaTrader5` update regardless of update type.

### 2. Documentation

- **CONTRIBUTING.md** — short section: dependency updates arrive as Renovate
  PRs; digest/minor/patch auto-merge once `tests` passes; majors and any
  `MetaTrader5` bump need manual review.
- **SECURITY.md** — note SHA-pinning of GitHub Actions and `lockFileMaintenance`
  as supply-chain integrity controls.
- **CLAUDE.md** — brief note under conventions/gotchas: actions are SHA-pinned
  and dependencies are Renovate-managed; do not hand-bump or un-pin them.

## Prerequisites (manual, by the maintainer)

These cannot be done from the repo and must be done in the GitHub UI:

1. Install the **Renovate GitHub App** on `tanem/mt5-pnl-exporter`.
2. Enable **"Allow auto-merge"** in the repository settings (Renovate's
   auto-merge relies on GitHub's native auto-merge feature).

After install, Renovate opens an onboarding PR plus the digest-pinning PR.

## Verification

- Validate config: `npx --yes renovate-config-validator renovate.json`.
- No application code changes, so the existing `pytest` / `ruff` / `mypy` suite
  is unaffected and CI stays green.

## Out of scope

- Dependabot (Renovate chosen instead).
- Hand-pinning action SHAs (Renovate does it).
- README changes.
- Any change to the publish flow (stays a manual tag).
- CI improvements surfaced during brainstorming but deliberately deferred:
  Windows test runner, Python-version matrix, uv CI cache, CodeQL/SAST. None
  are required for this work.
