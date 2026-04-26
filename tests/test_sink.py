"""Tests for WikiArticleSink."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from ladon.networking import AsyncHttpClient
from ladon.networking.config import HttpClientConfig

from ladon_mimir.api import DEFAULT_USER_AGENT
from ladon_mimir.models import ArticleRecord
from ladon_mimir.refs import ArticleRef
from ladon_mimir.sink import LeafUnavailableError, WikiArticleSink


@pytest.fixture
def client() -> AsyncHttpClient:
    return AsyncHttpClient(
        HttpClientConfig(
            default_headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout_seconds=5.0,
        )
    )


def _record(
    page_id: int = 1,
    title: str = "Black–Scholes model",
    full_text: str = "First para.\n\nRest of article.",
) -> ArticleRecord:
    return ArticleRecord(
        page_id=page_id,
        title=title,
        summary="First para.",
        full_text=full_text,
        categories=("Mathematical finance",),
        last_modified=datetime(2024, 1, 1, tzinfo=timezone.utc),
        word_count=len(full_text.split()),
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
    )


def _ref(page_id: int = 1, title: str = "Black–Scholes model") -> ArticleRef:
    return ArticleRef(
        page_id=page_id,
        title=title,
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
    )


async def test_consume_happy_path(client: AsyncHttpClient) -> None:
    expected = _record()
    with patch(
        "ladon_mimir.sink._fetch_article", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = expected
        sink = WikiArticleSink()
        result = await sink.consume(_ref(), client)

    assert result == expected
    mock_fetch.assert_awaited_once_with("Black–Scholes model", client)


async def test_consume_not_found_raises(client: AsyncHttpClient) -> None:
    with patch(
        "ladon_mimir.sink._fetch_article", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = None
        sink = WikiArticleSink()
        with pytest.raises(LeafUnavailableError, match="article not found"):
            await sink.consume(_ref(title="NonExistent"), client)


async def test_word_count_computed(client: AsyncHttpClient) -> None:
    text = "one two three four five six seven"
    record = _record(full_text=text)
    with patch(
        "ladon_mimir.sink._fetch_article", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = record
        sink = WikiArticleSink()
        result = await sink.consume(_ref(), client)

    assert result.word_count == 7


async def test_last_modified_is_utc_aware(client: AsyncHttpClient) -> None:
    record = _record()
    with patch(
        "ladon_mimir.sink._fetch_article", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = record
        sink = WikiArticleSink()
        result = await sink.consume(_ref(), client)

    assert result.last_modified.tzinfo is not None


async def test_consume_wrong_ref_type_raises(client: AsyncHttpClient) -> None:
    sink = WikiArticleSink()
    with pytest.raises(TypeError, match="expected ArticleRef"):
        await sink.consume("not-a-ref", client)
