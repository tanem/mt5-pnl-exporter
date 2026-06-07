# Contributing

Thanks for your interest. This is a small project — issues and PRs are welcome.

## One-time setup

```bash
uv sync                              # install dependencies
uv run pre-commit install            # enable the gitleaks secret-scan hook
```

## Running tests and hooks

```bash
uv run pytest                        # run the test suite (coverage gate: ≥95%)
uv run pre-commit run --all-files    # run the gitleaks hook manually
uv run ruff check src/ tests/        # lint
uv run ruff format --check src/ tests/  # check formatting
uv run mypy src/mt5_pnl_exporter     # type-check
```

## Regenerating the schema

After editing the `Snapshot` model or any of its nested models in `snapshot.py`, regenerate `schema/snapshot.schema.json`:

```bash
uv run mt5-pnl-exporter schema
```

`tests/test_schema_file.py` fails CI if the committed schema drifts from the model. Commit the regenerated file alongside the model change.

## Smoke-test a real export

Before publishing a new version, exercise a real MT5 export from your working tree. `MetaTrader5` is Windows-only, so this runs on the Windows host where MT5 lives — the cross-platform checks (`pytest`, `ruff`, `mypy`) run anywhere.

1. Prepare the host once — see the README's [Prepare the MT5 host](README.md#prepare-the-mt5-host) section (dedicated terminal + first-run login).
2. `uv sync --extra mt5` — install dependencies including `MetaTrader5` from the clone.
3. Store credentials if you haven't already: `uv run mt5-pnl-exporter set-investor-password <login>` and `uv run mt5-pnl-exporter set-encryption-passphrase`.
4. `cp config.example.yaml config.yaml` and fill in `terminal_path` and `accounts`.
5. `uv run mt5-pnl-exporter export` — confirm it logs `OK` per account and writes the snapshot.

Steps 2–5 test the code in your working tree. To also test the **packaged artifact** a consumer installs (entry point, the `[mt5]` extra, the bundled schema file), build and install the wheel before publishing:

```bash
uv build                                   # produces dist/*.whl
uv tool install "./dist/mt5_pnl_exporter-<ver>-py3-none-any.whl[mt5]"
mt5-pnl-exporter export                    # runs the installed tool, not the clone
```

## Dependency updates

Dependencies are kept current by [Renovate](https://docs.renovatebot.com/) (config: [`renovate.json`](renovate.json)), which manages both GitHub Actions and Python dependencies (`pyproject.toml` / `uv.lock`):

- GitHub Actions are pinned to commit SHAs (not mutable tags) for supply-chain integrity; Renovate keeps the SHA and its version comment current.
- Digest, minor, and patch updates **auto-merge** once the `tests` workflow passes.
- Major updates, and any `MetaTrader5` bump (Windows-only optional extra that CI cannot exercise), open a PR for manual review.
- `lockFileMaintenance` periodically refreshes `uv.lock` to pick up transitive security patches.

Don't hand-bump these versions — let Renovate's PRs flow through.

## Conventions

See [`CLAUDE.md`](CLAUDE.md) — the canonical reference for coding style, architectural rules, and gotchas (NZ English, no module-level `MetaTrader5` import, doc-sync rule, etc.). It's loaded automatically by Claude Code but reads as a normal project doc.
