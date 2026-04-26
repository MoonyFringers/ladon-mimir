"""WikiArticleSink — fetches and returns an ArticleRecord for a given ArticleRef."""

from __future__ import annotations

from ladon.networking import AsyncHttpClient

from .api import _fetch_article
from .models import ArticleRecord
from .refs import ArticleRef


class LeafUnavailableError(Exception):
    """Raised when a Wikipedia article cannot be found (missing or deleted page)."""


class WikiArticleSink:
    """Async sink that fetches full article content for a given ArticleRef.

    Delegates HTTP to ``_fetch_article``; retries are handled by the
    underlying ``AsyncHttpClient``. Raises ``LeafUnavailableError`` when
    the page does not exist, and lets HTTP errors propagate so the runner
    can apply its own error policy.
    """

    async def consume(
        self, ref: object, client: AsyncHttpClient
    ) -> ArticleRecord:
        if not isinstance(ref, ArticleRef):
            raise TypeError(f"expected ArticleRef, got {type(ref).__name__}")
        record = await _fetch_article(ref.title, client)
        if record is None:
            raise LeafUnavailableError(
                f"article not found: {ref.title!r} (page_id={ref.page_id})"
            )
        return record
