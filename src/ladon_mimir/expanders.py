"""WikiCategoryExpander — async BFS traversal of a Wikipedia category tree."""

from __future__ import annotations

import asyncio

from ladon import Expansion
from ladon.networking import AsyncHttpClient

from .api import MembersResult, _fetch_members
from .models import CategoryRecord
from .refs import ArticleRef, CategoryRef


class WikiCategoryExpander:
    """Async BFS expander for a Wikipedia category tree.

    Traverses sub-categories up to *max_depth* levels deep, collecting
    unique article references. Same-level sub-categories are fetched
    concurrently via ``asyncio.gather``.

    Args:
        max_depth: Maximum sub-category recursion depth (0 = root only).
        skip_page_ids: Article page IDs to exclude from output — used to
            resume an interrupted crawl without re-fetching already-stored
            articles.
        category_blocklist: Sub-category titles to skip during traversal.
            Useful to prune domain-contaminating sub-trees (e.g. "Regression
            analysis" when targeting mathematical finance only).
    """

    def __init__(
        self,
        max_depth: int = 2,
        skip_page_ids: frozenset[int] = frozenset(),
        category_blocklist: frozenset[str] = frozenset(),
    ) -> None:
        self._max_depth = max_depth
        self._skip_page_ids = skip_page_ids
        self._category_blocklist = category_blocklist

    async def expand(self, ref: object, client: AsyncHttpClient) -> Expansion:
        """Expand *ref* into a flat list of unique article references.

        *ref* must be a ``CategoryRef``; the ``object`` annotation satisfies
        the ``AsyncExpander`` protocol's contravariant parameter requirement.

        Returns an ``Expansion`` containing a ``CategoryRecord`` (article
        count after dedup) and the deduplicated ``ArticleRef`` list.
        """
        if not isinstance(ref, CategoryRef):
            raise TypeError(f"expected CategoryRef, got {type(ref).__name__}")
        seen: set[int] = set(self._skip_page_ids)
        articles: list[ArticleRef] = []
        await self._bfs(
            ref.title, depth=0, client=client, seen=seen, out=articles
        )
        return Expansion(
            record=CategoryRecord(title=ref.title, article_count=len(articles)),
            child_refs=articles,
        )

    async def _bfs(
        self,
        title: str,
        depth: int,
        client: AsyncHttpClient,
        seen: set[int],
        out: list[ArticleRef],
    ) -> None:
        # seen and out are shared across all recursive calls within one expand()
        # invocation — safe because asyncio is single-threaded within an event loop.
        members: MembersResult = await _fetch_members(title, client)

        for article in members.articles:
            if article.page_id not in seen:
                seen.add(article.page_id)
                out.append(article)

        if depth < self._max_depth and members.sub_categories:
            await asyncio.gather(
                *[
                    self._bfs(sub, depth + 1, client, seen, out)
                    for sub in members.sub_categories
                    if sub not in self._category_blocklist
                ]
            )
