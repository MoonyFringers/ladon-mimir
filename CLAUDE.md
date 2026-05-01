# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project description

`ladon-mimir` is an **async Wikipedia adapter** for the Ladon crawler
framework. It crawls Wikipedia's mathematical finance category tree and
persists articles to DuckDB for LLM fine-tuning corpus generation.

Repository layout:

```text
src/ladon_mimir/        ← adapter source
  plugin.py            ← AsyncCrawlPlugin composition
  source.py            ← category Source
  expander.py          ← category / page Expander
  sink.py              ← DuckDB Sink
  repo.py              ← DuckDB repository (ladon_runs + mimir_articles)
  cli.py               ← ladon-mimir CLI entry point
tests/                 ← pytest test suite (pytest-asyncio + pytest-httpx)
```

## Design reference

This adapter implements the Ladon async SES protocol. Before making
structural changes, consult:
- [Ladon SES protocol ADR-004](https://github.com/MoonyFringers/ladon/blob/main/docs/decisions/adr-004-ses-protocol-design.md)
- [Ladon persistence ADR-006](https://github.com/MoonyFringers/ladon/blob/main/docs/decisions/adr-006-persistence-layer.md)
- [Ladon ADR index](https://github.com/MoonyFringers/ladon/blob/main/docs/decisions/index.md)

## Language policy

English only — source code, comments, commit messages, documentation.

## Common commands

```sh
# Install Ladon core
pip install git+https://github.com/MoonyFringers/ladon.git

# Install this package and dev dependencies
pip install -e ".[dev]"

# Install git hooks (run once after cloning)
pre-commit install

# Run tests
pytest tests/ -v

# Run the crawler
ladon-mimir crawl --category "Mathematical_finance" --db mimir.db
```

## Dev commands

```sh
pytest tests/ -v                    # run test suite
pytest tests/ -v --cov              # with coverage
black src/ tests/                   # format
ruff check src/ tests/              # lint
isort src/ tests/                   # sort imports
pyright                             # type-check (strict)
pre-commit run --all-files          # run all hooks at once
```

## Tests

- Tests use `pytest-asyncio` (asyncio_mode = "auto") and `pytest-httpx` for
  HTTP mocking — do not introduce real HTTP calls in tests.
- All tests must pass before committing.
- New behaviour must be covered by tests.
- Fix source code, not tests, when there is a mismatch.

## Commits and PRs

- Sign commits with `git commit -S` (GPG); wrap subjects to 72 characters
  and bodies to 80 columns
- Follow **Conventional Commits with scope**:
  `feat(crawler): ...`, `fix(db): ...`, `feat(resume): ...`

  Common scopes: `crawler`, `db`, `resume`, `cli`, `tests`, `docs`, `deps`

- Include `Fixes: #<issue-number>` in the commit footer when resolving an
  issue
- Do not add `Co-Authored-By:` trailers for Claude
- Open a tracking issue before starting implementation work
- Every PR must target upstream `origin` and reference the tracking issue
