"""Wikipedia MediaWiki API helpers.

All HTTP calls go through AsyncHttpClient. No direct httpx usage here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from ladon.networking import AsyncHttpClient
from ladon.networking.errors import HttpClientError

from .models import ArticleRecord
from .refs import ArticleRef

WIKI_API = "https://en.wikipedia.org/w/api.php"

DEFAULT_USER_AGENT = (
    "ladon-mimir/0.1.0 "
    "(https://github.com/MoonyFringers/ladon-mimir; feeder81@gmail.com)"
)


@dataclass
class MembersResult:
    articles: list[ArticleRef]
    sub_categories: list[str]


async def _fetch_members(title: str, client: AsyncHttpClient) -> MembersResult:
    """Fetch direct members of a Wikipedia category (articles + sub-categories).

    Handles cmcontinue pagination automatically.
    """
    articles: list[ArticleRef] = []
    sub_categories: list[str] = []
    cmcontinue: str | None = None

    while True:
        params: dict[str, str] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{title}",
            "cmtype": "subcat|page",
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue is not None:
            params["cmcontinue"] = cmcontinue

        url = f"{WIKI_API}?{urlencode(params)}"
        result = await client.get(url)

        if not result.ok:
            raise HttpClientError(
                f"Wikipedia API error for category '{title}': {result.error}"
            )

        data: Any = json.loads(result.value)  # type: ignore[arg-type]
        members: list[Any] = data.get("query", {}).get("categorymembers", [])

        for member in members:
            ns: int | None = member.get("ns")
            page_id = int(member["pageid"])
            page_title = str(member["title"])
            if ns == 0:
                articles.append(
                    ArticleRef(
                        page_id=page_id,
                        title=page_title,
                        url=f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                    )
                )
            elif ns == 14:
                sub_categories.append(page_title.removeprefix("Category:"))

        cont: Any = data.get("continue")
        if cont is None:
            break
        cmcontinue = str(cont.get("cmcontinue", ""))
        if not cmcontinue:
            break

    return MembersResult(articles=articles, sub_categories=sub_categories)


async def _fetch_article(
    title: str, client: AsyncHttpClient
) -> ArticleRecord | None:
    """Fetch a single Wikipedia article by title.

    Returns None if the page does not exist.
    """
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|categories|info",
        "explaintext": "1",
        "inprop": "url",
        "cllimit": "50",
        "format": "json",
    }
    url = f"{WIKI_API}?{urlencode(params)}"
    result = await client.get(url)

    if not result.ok:
        raise HttpClientError(
            f"Wikipedia API error for article '{title}': {result.error}"
        )

    data: Any = json.loads(result.value)  # type: ignore[arg-type]
    pages: Any = data.get("query", {}).get("pages", {})

    # MediaWiki returns a single key per title; -1 means missing
    page_id_str, page = next(iter(pages.items()))
    if page_id_str == "-1":
        return None

    page_id = int(page_id_str)
    full_text: str = str(page.get("extract", ""))
    summary = full_text.split("\n\n")[0] if full_text else ""

    raw_categories: list[Any] = page.get("categories", [])
    categories = tuple(
        str(c["title"]).removeprefix("Category:")
        for c in raw_categories
        if "title" in c
    )

    touched: str = str(page.get("touched", ""))
    last_modified = _parse_touched(touched)

    canonical_url: str = str(page.get("fullurl", ""))

    return ArticleRecord(
        page_id=page_id,
        title=str(page.get("title", title)),
        summary=summary,
        full_text=full_text,
        categories=categories,
        last_modified=last_modified,
        word_count=len(full_text.split()),
        url=canonical_url,
    )


def _parse_touched(touched: str) -> datetime:
    """Parse a MediaWiki 'touched' timestamp (ISO 8601) to a tz-aware UTC datetime."""
    if not touched:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(touched.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=timezone.utc)
