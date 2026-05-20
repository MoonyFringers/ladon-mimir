# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.2.0] — 2026-05-20

### Added

- **`MimirMCPAdapter`** — implements `LadonMCPAdapter` from `ladon-crawl>=0.3.1`,
  registering two MCP data-plane tools and one resource:
  - `mimir_article_search(query, limit=10)` — keyword search across title,
    summary, and full text; results ordered by word count descending.
  - `mimir_corpus_stats()` — total article and word counts, date range.
  - `ladon://mimir/articles/{page_id}` resource — full Markdown article content.
- **Entry point** — `ladon.mcp` group entry `mimir = ladon_mimir.mcp:MimirMCPAdapter`;
  installing ladon-mimir alongside ladon-nous is sufficient to activate mimir tools.

### Changed

- Minimum `ladon-crawl` dependency bumped from `>=0.2.0` to `>=0.3.1` to pick
  up the `LadonMCPAdapter` ABC.

---

## [0.1.0] — 2026-04-26

### Added

- `WikiCategorySource` — single-ref source returning the root `CategoryRef` for protocol completeness.
- `WikiCategoryExpander` — async BFS traversal of a Wikipedia category tree via `asyncio.gather`; configurable `max_depth`, `skip_page_ids` for resume, and `category_blocklist` for pruning.
- `WikiArticleSink` — async sink that fetches full article text via the MediaWiki Action API (`prop=extracts|categories|info`); raises `LeafUnavailableError` for missing pages.
- `MimirPlugin` — `AsyncCrawlPlugin`-compatible bundle wiring source, expander, and sink.
- `MimirRepository` — DuckDB-backed persistence: `mimir_articles` (upsert on `page_id`) and `ladon_runs` (run lifecycle with fetched/failed counters). Context manager support; `get_existing_page_ids()` for resume.
- `export_parquet(db_path, parquet_path) -> int` — bulk export of `mimir_articles` to Parquet via DuckDB's native `COPY … TO … FORMAT PARQUET`.
- `ladon-mimir` CLI entrypoint — `--category`, `--out`, `--concurrency`, `--depth`, `--limit`, `--exclude-category`, `--sync`, `--dry-run`, `--verbose`.
- Public models: `ArticleRecord`, `CategoryRecord`, `SubCategoryRecord`, `ArticleRef`, `CategoryRef`.
- 66 tests covering all layers: models, API helpers, expander BFS, sink, repository, storage, and CLI.

[Unreleased]: https://github.com/MoonyFringers/ladon-mimir/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/MoonyFringers/ladon-mimir/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MoonyFringers/ladon-mimir/releases/tag/v0.1.0
