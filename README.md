# ladon-mimir

Async Wikipedia adapter for [Ladon](https://github.com/MoonyFringers/ladon) — crawls the `Category:Mathematical_finance` corpus and exports a structured dataset for LLM fine-tuning.

> **Status**: pre-release — implementation in progress.

## Overview

`ladon-mimir` is a first-party adapter that demonstrates Ladon's async crawling capabilities against a real-world, publicly licensed dataset. It traverses Wikipedia's mathematical finance category tree (BFS, configurable depth), fetches full article text via the MediaWiki API, and persists results to [DuckDB](https://duckdb.org/) with Parquet export.

## License

Apache-2.0. See [LICENSE](LICENSE).
