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

## Conventions

- NZ English in comments and docs (realise, behaviour, colour).
- Never import `MetaTrader5` at module level. Keep it deferred inside `MT5Source` (`sources/mt5.py`) so commands like `schema` work on machines without the `MetaTrader5` package installed.
- Tests use a fake `DataSource` injected in place of `MT5Source` — never mock the `MetaTrader5` package directly.
- After changing commands, architecture, or gotchas, update both `README.md` and `CLAUDE.md` in the same change.
