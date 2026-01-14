# Repository Guidelines

## Project Structure & Module Organization

- `withings_exporter/`: core package (CLI, OAuth, API client, storage, export, scheduling).
- `tests/`: placeholder for automated tests (currently empty).
- `debug_*.py`: ad-hoc scripts for manual API checks and troubleshooting.
- `config.yaml.template`: sample config used to bootstrap `~/.withings/config.yaml`.
- `README.md`: user-facing setup, CLI usage, and configuration details.

## Build, Test, and Development Commands

- `uv pip install -e .`: install in editable mode (recommended).
- `pip install -e .`: editable install if you do not use `uv`.
- `withings-exporter setup`: configure OAuth and create `~/.withings/.env`.
- `withings-exporter sync --start-date 2010-01-01`: full historical sync.
- `withings-exporter export --format json`: export data for analysis.
- `pytest tests/`: run tests (no automated tests yet).

## Coding Style & Naming Conventions

- Python 3.9+; follow standard PEP 8 style.
- Indentation: 4 spaces, no tabs.
- Naming: `snake_case` for functions/vars, `CamelCase` for classes, `UPPER_SNAKE_CASE` for constants.
- No enforced formatter or linter is configured; keep changes tidy and consistent with nearby code.

## Testing Guidelines

- There are currently no automated tests. New test files should live in `tests/` and be named `test_*.py`.
- For manual verification, use the debug scripts (for example, `debug_api.py`) or run a narrow sync/export range.

## Commit & Pull Request Guidelines

- Commit messages are simple, sentence-style summaries (see `git log -5`), without strict prefixes.
- PRs should describe the user impact, list key changes, and note any manual verification performed.
- Include screenshots only if changing CLI output or generated files in a visible way.

## Security & Configuration Notes

- Credentials live in `~/.withings/.env`; tokens in `~/.withings/credentials.json` (both should be `0600`).
- Data is stored locally in `~/.withings/health_data.db`; exports default to `~/.withings/exports/`.
- The Withings API rate limit is 120 requests/minute; prefer small date ranges while iterating.
