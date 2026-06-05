# Node.js 20 GHA deprecation follow-up

Status: design. Ready to plan implementation once approved.

Standalone maintenance follow-up. Not part of Phase 1b's cycle
sequence (cycles 1–6 are merged) and not the post-1.0-publish
follow-up (that PR — trusted-publish workflow + `pyproject`
classifiers/urls/inline `license`) is still pending the manual tag
and PyPI publish. This PR lands between the cycle-6 merge and the
1.0.0 tag to remove a known deprecation that would otherwise bite CI
ten days from now.

## Why

The cycle-6 main-branch CI run on 2026-06-05 surfaced GitHub's
Node.js 20 deprecation warning. The notice names four actions as
running on Node 20 today:

- `actions/checkout@v4`
- `actions/setup-python@v5`
- `astral-sh/setup-uv@v4`
- `actions/github-script@60a0d83…` (transitive — loaded by
  `codecov/codecov-action@v5`, not a direct dependency)

GitHub will force-run Node 20 actions on Node 24 starting
**2026-06-16** (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` becomes the
default), and remove the Node 20 runtime from the runners on
**2026-09-16**. The force-bump is meant to be safe, but most actions
have already shipped explicit Node 24 majors — moving the repo to
those majors removes the "running on the wrong Node by default"
warning and surfaces any genuine breakage now rather than after the
deadline.

Doing this before the 1.0.0 git tag keeps `main` clean for the tag —
the tag should land on a `main` whose CI is fully current.

## Deliverables

Four version bumps in `.github/workflows/ci.yml`. No other files.

| Action | From | To |
| --- | --- | --- |
| `actions/checkout` | `@v4` | `@v6` |
| `actions/setup-python` | `@v5` | `@v6` |
| `astral-sh/setup-uv` | `@v4` | `@v8` |
| `codecov/codecov-action` | `@v5` | `@v6` |

Each is the current latest major. All four are documented as
Node 24-compatible.

## Per-action notes

### `actions/checkout`: v4 → v6

Two majors skipped (v5 was the Node 24 transition; v6 is the current
default). Our usage is `- uses: actions/checkout@v4` with no `with:`
inputs — the most conservative consumer of the action. Latest-major
bump is safe.

### `actions/setup-python`: v5 → v6

One major. Our usage:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
```

`python-version` is the canonical input across v3–v6 and won't change
shape. v6 introduces some opt-in behaviour around caching and
glibc-aware downloads — none of which we opt into.

### `astral-sh/setup-uv`: v4 → v8

Four majors. Largest jump in the bundle. Our usage is the bare
`- uses: astral-sh/setup-uv@v4` with no `with:` inputs — we just want
`uv` available on `PATH`. The v8 `action.yml` defines many inputs
(`version`, `python-version`, `activate-environment`, `enable-cache`,
…) — all additive, none required. The default install-and-PATH
behaviour is stable across v4–v8.

If CI surfaces a behaviour change on the PR run, fall back to `@v7`
(the major immediately before v8). That decision lives in the plan,
not the spec — only invoke it if needed.

### `codecov/codecov-action`: v5 → v6

One major. **Verified directly against `action.yml` in the v6
release:** the three inputs we use (`token`, `slug`, `files`) are all
still present and unchanged. The v6.0.0 release notes confirm the
sole intent of the major bump was upgrading the transitive
`actions/github-script` dependency to v8 (Node 24). No input
renames, no behaviour change for callers using passphrase-style
token uploads.

Bumping codecov-action to v6 is the only way to remove the transitive
`github-script` Node 20 warning that GitHub's notice flags — we have
no other direct dependency on `github-script`.

## Verification

The PR's own CI run is the test. The `tests` workflow exercises every
step that depends on these actions:

- `checkout` sets up the working tree (failure mode: workflow can't
  start).
- `setup-python` provides Python 3.12 (failure mode: `uv sync` fails
  to find a compatible interpreter).
- `setup-uv` provides `uv` (failure mode: `uv` not on PATH).
- The `pytest --cov-report=xml` step produces `coverage.xml`, then
  `codecov-action` uploads it (failure mode: upload error visible in
  the job log; the action stays non-fatal so the job still passes).

If any of these break, the PR run surfaces it directly. No new tests
are needed.

## Branching and PR

Branch `chore-node20-deprecation` from `main` (currently `e0d2b60`,
the cycle-6 merge). No direct pushes to `main`. PR is **regular**
(not draft) — opens ready for review immediately, per the standing
preference.

Plan ends with: commit changes → push branch → open PR → wait for CI
green.

**PR title:** `ci: bump GHA actions off Node 20 (deadline 2026-06-16)`

## Out of scope (deliberately)

- **Renovate / Dependabot config** to keep these actions current
  automatically. Worth doing, but a separate decision driven by how
  much GHA-action churn the project wants to accept passively.
- **SHA-pinning the actions** (the `uses: actions/checkout@<sha>`
  pattern recommended by GitHub Security). Improves supply-chain
  posture; comes with the cost of manual updates and unreadable
  diffs. Separate decision.
- **README / CLAUDE.md edits.** Neither file mentions these actions
  or their versions; nothing rots from a workflow-only bump.
- **Workflow-level Node version pinning** (e.g. forcing
  `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` or
  `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` as an env var). Pinning
  via the action major version is cleaner and self-documenting.
- **Anything else in the post-1.0-publish follow-up** (trusted-publish
  workflow, `pyproject` classifiers / urls / inline `license`).
  Lands after the manual `1.0.0` tag and first `uv publish`.

## Out of order: the 1.0 tag

The cycle-4 spec's post-merge sequence says cycles 4 + 5 + 6 all on
`main` → manual `1.0.0` tag → manual `uv publish` → follow-up PR.
This deprecation PR slips in between cycle-6's merge and the tag,
because the GitHub deadline (2026-06-16) is sooner than any realistic
publish date and a clean CI surface on the tagged commit matters.
After this PR merges, the tag/publish sequence proceeds as previously
planned.
