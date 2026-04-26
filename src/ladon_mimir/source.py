"""WikiCategorySource — produces a single CategoryRef for the target category."""

from __future__ import annotations

from ladon.networking import AsyncHttpClient

from .refs import CategoryRef


class WikiCategorySource:
    """Single-ref source for a Wikipedia category.

    Always returns one ``CategoryRef`` for *category*. The source is present
    for protocol completeness; it makes ``MimirPlugin`` usable via the standard
    Ladon runner without special-casing.
    """

    def __init__(self, category: str) -> None:
        self._category = category

    async def discover(self, client: AsyncHttpClient) -> list[CategoryRef]:
        return [CategoryRef(title=self._category)]
