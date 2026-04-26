"""Tests for ladon_mimir.api — Wikipedia MediaWiki API helpers.

All HTTP is intercepted via pytest-httpx (no real network calls).
"""

from __future__ import annotations

import json
from datetime import timezone

import pytest
from ladon.networking import AsyncHttpClient
from ladon.networking.config import HttpClientConfig
from pytest_httpx import HTTPXMock

from ladon_mimir.api import (
    DEFAULT_USER_AGENT,
    WIKI_API,
    _fetch_article,
    _fetch_members,
)
from ladon_mimir.models import ArticleRecord
from ladon_mimir.refs import ArticleRef

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> AsyncHttpClient:
    return AsyncHttpClient(
        HttpClientConfig(
            default_headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout_seconds=5.0,
        )
    )


def _members_response(
    articles: list[dict[str, object]],
    subcats: list[dict[str, object]],
    cont: str | None = None,
) -> bytes:
    body: dict[str, object] = {"query": {"categorymembers": articles + subcats}}
    if cont:
        body["continue"] = {"cmcontinue": cont, "continue": "-||"}
    return json.dumps(body).encode()


def _article_response(
    page_id: int,
    title: str,
    extract: str = "First para.\n\nRest of article.",
    categories: list[str] | None = None,
    touched: str = "2024-01-15T12:00:00Z",
    fullurl: str = "",
) -> bytes:
    cats = [{"title": f"Category:{c}"} for c in (categories or [])]
    body = {
        "query": {
            "pages": {
                str(page_id): {
                    "pageid": page_id,
                    "title": title,
                    "extract": extract,
                    "categories": cats,
                    "touched": touched,
                    "fullurl": fullurl
                    or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                }
            }
        }
    }
    return json.dumps(body).encode()


def _missing_page_response() -> bytes:
    body = {"query": {"pages": {"-1": {"title": "NonExistent", "missing": ""}}}}
    return json.dumps(body).encode()


# ---------------------------------------------------------------------------
# _fetch_members tests
# ---------------------------------------------------------------------------


async def test_fetch_members_articles_and_subcats(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        url=f"{WIKI_API}?action=query&list=categorymembers"
        "&cmtitle=Category%3AMathematical_finance"
        "&cmtype=subcat%7Cpage&cmlimit=500&format=json",
        content=_members_response(
            articles=[{"pageid": 1, "ns": 0, "title": "Black–Scholes model"}],
            subcats=[
                {"pageid": 100, "ns": 14, "title": "Category:Financial models"}
            ],
        ),
    )
    result = await _fetch_members("Mathematical_finance", client)
    assert len(result.articles) == 1
    assert result.articles[0] == ArticleRef(
        page_id=1,
        title="Black–Scholes model",
        url="https://en.wikipedia.org/wiki/Black–Scholes_model",
    )
    assert result.sub_categories == ["Financial models"]


async def test_fetch_members_pagination(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    # Page 1 — returns cmcontinue token
    httpx_mock.add_response(
        content=_members_response(
            articles=[{"pageid": 1, "ns": 0, "title": "Article A"}],
            subcats=[],
            cont="token123",
        ),
    )
    # Page 2 — no continuation
    httpx_mock.add_response(
        content=_members_response(
            articles=[{"pageid": 2, "ns": 0, "title": "Article B"}],
            subcats=[],
        ),
    )
    result = await _fetch_members("SomeCategory", client)
    assert len(result.articles) == 2
    assert result.articles[0].title == "Article A"
    assert result.articles[1].title == "Article B"


async def test_fetch_members_empty_category(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_members_response(articles=[], subcats=[]),
    )
    result = await _fetch_members("EmptyCategory", client)
    assert result.articles == []
    assert result.sub_categories == []


async def test_fetch_members_strips_category_prefix(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_members_response(
            articles=[],
            subcats=[
                {"pageid": 50, "ns": 14, "title": "Category:Actuarial science"}
            ],
        ),
    )
    result = await _fetch_members("Mathematical_finance", client)
    assert result.sub_categories == ["Actuarial science"]


# ---------------------------------------------------------------------------
# _fetch_article tests
# ---------------------------------------------------------------------------


async def test_fetch_article_field_mapping(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_article_response(
            page_id=42,
            title="Itô calculus",
            extract="First paragraph.\n\nSecond paragraph.",
            categories=["Stochastic calculus", "Mathematical finance"],
            touched="2024-03-10T08:30:00Z",
            fullurl="https://en.wikipedia.org/wiki/It%C3%B4_calculus",
        ),
    )
    record = await _fetch_article("Itô calculus", client)
    assert isinstance(record, ArticleRecord)
    assert record.page_id == 42
    assert record.title == "Itô calculus"
    assert record.url == "https://en.wikipedia.org/wiki/It%C3%B4_calculus"
    assert record.categories == ("Stochastic calculus", "Mathematical finance")
    assert record.last_modified.tzinfo is not None
    assert record.last_modified.tzinfo == timezone.utc


async def test_fetch_article_summary_extraction(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_article_response(
            page_id=1,
            title="Test Article",
            extract="First paragraph text.\n\nSecond paragraph text.",
        ),
    )
    record = await _fetch_article("Test Article", client)
    assert record is not None
    assert record.summary == "First paragraph text."
    assert record.full_text == "First paragraph text.\n\nSecond paragraph text."


async def test_fetch_article_category_prefix_stripped(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_article_response(
            page_id=1,
            title="Test",
            categories=["Mathematical finance", "Stochastic processes"],
        ),
    )
    record = await _fetch_article("Test", client)
    assert record is not None
    for cat in record.categories:
        assert not cat.startswith("Category:")


async def test_fetch_article_not_found(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(content=_missing_page_response())
    record = await _fetch_article("NonExistent", client)
    assert record is None


async def test_fetch_article_word_count(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    text = "one two three four five"
    httpx_mock.add_response(
        content=_article_response(page_id=1, title="WordCount", extract=text),
    )
    record = await _fetch_article("WordCount", client)
    assert record is not None
    assert record.word_count == 5


async def test_fetch_article_last_modified_is_utc_aware(
    httpx_mock: HTTPXMock, client: AsyncHttpClient
) -> None:
    httpx_mock.add_response(
        content=_article_response(
            page_id=1,
            title="Test",
            touched="2024-06-01T00:00:00Z",
        ),
    )
    record = await _fetch_article("Test", client)
    assert record is not None
    assert record.last_modified.tzinfo is not None
