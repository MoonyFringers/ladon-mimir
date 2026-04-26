"""MimirPlugin — AsyncCrawlPlugin for Wikipedia category crawling."""

from __future__ import annotations

from .expanders import WikiCategoryExpander
from .sink import WikiArticleSink
from .source import WikiCategorySource


class MimirPlugin:
    """Ladon async crawl plugin for a Wikipedia category corpus.

    Wires together ``WikiCategorySource``, ``WikiCategoryExpander``, and
    ``WikiArticleSink`` into a single ``AsyncCrawlPlugin``-compatible bundle.

    Args:
        category: Wikipedia category name without the ``Category:`` prefix.
        max_depth: BFS depth for sub-category traversal (default: 2).
        skip_page_ids: Article page IDs to exclude — used for resume.
        category_blocklist: Sub-category titles to prune from BFS traversal.
    """

    def __init__(
        self,
        category: str,
        max_depth: int = 2,
        skip_page_ids: frozenset[int] = frozenset(),
        category_blocklist: frozenset[str] = frozenset(),
    ) -> None:
        self._name = "ladon_mimir"
        self._source = WikiCategorySource(category)
        self._expanders = [
            WikiCategoryExpander(
                max_depth=max_depth,
                skip_page_ids=skip_page_ids,
                category_blocklist=category_blocklist,
            )
        ]
        self._sink = WikiArticleSink()

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> WikiCategorySource:
        return self._source

    @property
    def expanders(self) -> list[WikiCategoryExpander]:
        return self._expanders

    @property
    def sink(self) -> WikiArticleSink:
        return self._sink
