"""Command-line entry point for the ladon-mimir Wikipedia adapter.

Usage::

    ladon-mimir --category "Mathematical finance" --out mimir.db
    ladon-mimir --category "Mathematical finance" --out mimir.db --sync
    ladon-mimir --category "Mathematical finance" --out mimir.db --depth 3 \\
        --concurrency 5 --limit 200 --exclude-category "Stubs"

Each invocation crawls one Wikipedia category tree via BFS, persisting
articles to a DuckDB database.  Re-running against the same ``--out`` file
resumes automatically — already-stored page IDs are skipped.

Output
------
Progress is written to stdout::

    Crawling "Mathematical finance" → mimir.db  (42 articles already stored)
    Done — 127 articles · 3 failed
      → Exported 127 articles to mimir.parquet

Pass ``--verbose`` to also see DEBUG-level messages from the Ladon framework
(leaf-level warnings, HTTP timings).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from ladon import async_run_crawl
from ladon.networking import AsyncHttpClient
from ladon.networking.config import HttpClientConfig
from ladon.runner import RunConfig

from . import __version__
from .models import ArticleRecord, CategoryRecord
from .plugin import MimirPlugin
from .repository import MimirRepository
from .storage import export_parquet

logger = logging.getLogger(__name__)

_USER_AGENT = (
    f"ladon-mimir/{__version__} "
    "(https://github.com/MoonyFringers/ladon-mimir)"
)


async def _crawl(
    category: str,
    db_path: str,
    concurrency: int,
    depth: int,
    limit: int,
    exclude_categories: list[str],
) -> tuple[int, int]:
    """Run the async BFS crawl and persist results.

    Returns ``(articles_saved, articles_failed)``.
    """
    with MimirRepository(db_path) as repo:
        existing_ids = repo.get_existing_page_ids()
        repo.start_run(category)

        plugin = MimirPlugin(
            category=category,
            max_depth=depth,
            skip_page_ids=existing_ids,
            category_blocklist=frozenset(exclude_categories),
        )
        config = RunConfig(
            leaf_limit=limit,
            async_concurrency=concurrency,
        )
        client_config = HttpClientConfig(
            user_agent=_USER_AGENT,
            min_request_interval_seconds=0.2,
            retries=3,
        )

        async def on_leaf(record: object, parent: object) -> None:
            if isinstance(record, ArticleRecord) and isinstance(
                parent, CategoryRecord
            ):
                repo.save_article(record, parent)
            else:
                repo.record_failure()

        async with AsyncHttpClient(client_config) as client:
            root_refs = await plugin.source.discover(client)
            try:
                result = await async_run_crawl(
                    root_refs[0], plugin, client, config, on_leaf=on_leaf
                )
                repo.finish_run("done")
            except Exception:
                repo.finish_run("failed")
                raise

        return result.leaves_persisted, result.leaves_failed


async def _run(
    category: str,
    db_path: str,
    concurrency: int,
    depth: int,
    limit: int,
    exclude_categories: list[str],
    sync: bool,
    dry_run: bool,
) -> None:
    """Orchestrate a full crawl-and-export cycle."""
    limit_label = str(limit) if limit > 0 else "unlimited"

    if dry_run:
        with MimirRepository(db_path) as repo:
            existing = len(repo.get_existing_page_ids())
        print(f'Dry run — would crawl "{category}" → {db_path}')
        print(
            f"  depth={depth}  concurrency={concurrency}  limit={limit_label}"
        )
        if existing:
            print(
                f"  resume: {existing:,} articles already stored (would skip)"
            )
        if exclude_categories:
            joined = ", ".join(exclude_categories)
            print(f"  exclude: {joined}")
        if sync:
            parquet = _parquet_path(db_path)
            print(f"  --sync: would export to {parquet}")
        return

    with MimirRepository(db_path) as repo:
        existing = len(repo.get_existing_page_ids())

    resume_note = (
        f"  ({existing:,} articles already stored)" if existing else ""
    )
    print(f'Crawling "{category}" → {db_path}{resume_note}')

    saved, failed = await _crawl(
        category=category,
        db_path=db_path,
        concurrency=concurrency,
        depth=depth,
        limit=limit,
        exclude_categories=exclude_categories,
    )

    parts = [f"{saved:,} article{'s' if saved != 1 else ''}"]
    if failed:
        parts.append(f"{failed:,} failed")
    print("Done — " + " · ".join(parts))

    if sync:
        parquet = _parquet_path(db_path)
        count = export_parquet(db_path, parquet)
        print(f"  → Exported {count:,} articles to {parquet}")


def _parquet_path(db_path: str) -> str:
    """Derive a ``.parquet`` path from the ``.db`` path."""
    p = Path(db_path)
    return str(p.with_suffix(".parquet"))


def _positive_int(name: str) -> type:
    """Return an argparse type validator that enforces value >= 1."""

    def _check(value: str) -> int:
        try:
            n = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"{name} must be a positive integer (got {value!r})"
            ) from None
        if n < 1:
            raise argparse.ArgumentTypeError(f"{name} must be >= 1 (got {n})")
        return n

    return _check  # type: ignore[return-value]


def _non_negative_int(name: str) -> type:
    """Return an argparse type validator that enforces value >= 0."""

    def _check(value: str) -> int:
        try:
            n = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"{name} must be a non-negative integer (got {value!r})"
            ) from None
        if n < 0:
            raise argparse.ArgumentTypeError(f"{name} must be >= 0 (got {n})")
        return n

    return _check  # type: ignore[return-value]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ladon-mimir",
        description="Crawl a Wikipedia category tree into a DuckDB database.",
    )
    parser.add_argument(
        "--category",
        required=True,
        metavar="NAME",
        help="Wikipedia category name without the 'Category:' prefix.",
    )
    parser.add_argument(
        "--out",
        default="mimir.db",
        metavar="PATH",
        help="Output DuckDB database path (default: mimir.db).",
    )
    parser.add_argument(
        "--concurrency",
        type=_positive_int("--concurrency"),
        default=10,
        metavar="N",
        help="Maximum concurrent article fetches (default: 10).",
    )
    parser.add_argument(
        "--depth",
        type=_positive_int("--depth"),
        default=2,
        metavar="N",
        help="BFS depth for sub-category traversal (default: 2).",
    )
    parser.add_argument(
        "--limit",
        type=_non_negative_int("--limit"),
        default=0,
        metavar="N",
        help="Maximum articles to fetch; 0 means no limit (default: 0).",
    )
    parser.add_argument(
        "--exclude-category",
        dest="exclude_categories",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Sub-category title to prune from BFS traversal "
            "(repeatable, e.g. --exclude-category Stubs)."
        ),
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        default=False,
        help=(
            "After crawling, export mimir_articles to a Parquet file "
            "at the same path as --out but with a .parquet extension."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be done without actually crawling.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help=(
            "Enable verbose output: show DEBUG-level messages from the "
            "Ladon framework (leaf warnings, HTTP timings, etc.)."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    if not args.verbose:
        logging.getLogger("ladon").setLevel(logging.ERROR)

    asyncio.run(
        _run(
            category=args.category,
            db_path=args.out,
            concurrency=args.concurrency,
            depth=args.depth,
            limit=args.limit,
            exclude_categories=args.exclude_categories,
            sync=args.sync,
            dry_run=args.dry_run,
        )
    )
