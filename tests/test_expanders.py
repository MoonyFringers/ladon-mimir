"""Tests for WikiCategoryExpander — BFS traversal, dedup, depth cap, blocklist."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from ladon.networking import AsyncHttpClient
from ladon.networking.config import HttpClientConfig

from ladon_mimir.api import DEFAULT_USER_AGENT, MembersResult
from ladon_mimir.expanders import WikiCategoryExpander
from ladon_mimir.refs import ArticleRef, CategoryRef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ref(page_id: int, title: str = "") -> ArticleRef:
    return ArticleRef(
        page_id=page_id,
        title=title or f"Article {page_id}",
        url=f"https://en.wikipedia.org/wiki/Article_{page_id}",
    )


def _members(
    articles: list[ArticleRef] | None = None,
    sub_categories: list[str] | None = None,
) -> MembersResult:
    return MembersResult(
        articles=articles or [],
        sub_categories=sub_categories or [],
    )


@pytest.fixture
def client() -> AsyncHttpClient:
    return AsyncHttpClient(
        HttpClientConfig(
            default_headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout_seconds=5.0,
        )
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bfs_depth_0(client: AsyncHttpClient) -> None:
    """depth=0 returns only root articles, no sub-category recursion."""
    root_members = _members(
        articles=[_ref(1), _ref(2)], sub_categories=["Sub A"]
    )

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = root_members
        expander = WikiCategoryExpander(max_depth=0)
        result = await expander.expand(CategoryRef(title="Root"), client)

    assert mock_fetch.call_count == 1
    assert result.record.article_count == 2
    assert [r.page_id for r in result.child_refs] == [1, 2]


async def test_bfs_depth_1(client: AsyncHttpClient) -> None:
    """depth=1 fetches root + one sub-category level."""
    root_members = _members(articles=[_ref(1)], sub_categories=["Sub A"])
    sub_a_members = _members(articles=[_ref(2), _ref(3)])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [root_members, sub_a_members]
        expander = WikiCategoryExpander(max_depth=1)
        result = await expander.expand(CategoryRef(title="Root"), client)

    assert mock_fetch.call_count == 2
    assert result.record.article_count == 3
    assert {r.page_id for r in result.child_refs} == {1, 2, 3}


async def test_bfs_depth_2(client: AsyncHttpClient) -> None:
    """depth=2 fetches root + depth-1 + depth-2 sub-categories."""
    root_members = _members(articles=[_ref(1)], sub_categories=["Sub A"])
    sub_a_members = _members(articles=[_ref(2)], sub_categories=["Sub B"])
    sub_b_members = _members(articles=[_ref(3)])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [root_members, sub_a_members, sub_b_members]
        expander = WikiCategoryExpander(max_depth=2)
        result = await expander.expand(CategoryRef(title="Root"), client)

    assert mock_fetch.call_count == 3
    assert result.record.article_count == 3
    assert {r.page_id for r in result.child_refs} == {1, 2, 3}


async def test_deduplication(client: AsyncHttpClient) -> None:
    """Same page_id appearing in root and sub-category is counted once."""
    shared_ref = _ref(99, "Shared Article")
    root_members = _members(articles=[shared_ref], sub_categories=["Sub A"])
    sub_a_members = _members(articles=[shared_ref, _ref(1)])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [root_members, sub_a_members]
        expander = WikiCategoryExpander(max_depth=1)
        result = await expander.expand(CategoryRef(title="Root"), client)

    assert result.record.article_count == 2
    page_ids = [r.page_id for r in result.child_refs]
    assert page_ids.count(99) == 1


async def test_skip_page_ids(client: AsyncHttpClient) -> None:
    """Articles with pre-seeded page_ids are excluded from output."""
    root_members = _members(articles=[_ref(1), _ref(2), _ref(3)])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = root_members
        expander = WikiCategoryExpander(
            max_depth=0, skip_page_ids=frozenset({1, 3})
        )
        result = await expander.expand(CategoryRef(title="Root"), client)

    assert result.record.article_count == 1
    assert result.child_refs[0].page_id == 2


async def test_category_blocklist(client: AsyncHttpClient) -> None:
    """Blocked sub-categories are not recursed into."""
    root_members = _members(
        articles=[_ref(1)],
        sub_categories=["Allowed Sub", "Blocked Sub"],
    )
    allowed_members = _members(articles=[_ref(2)])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [root_members, allowed_members]
        expander = WikiCategoryExpander(
            max_depth=1,
            category_blocklist=frozenset({"Blocked Sub"}),
        )
        result = await expander.expand(CategoryRef(title="Root"), client)

    # "Blocked Sub" never fetched; only root + "Allowed Sub" = 2 calls
    assert mock_fetch.call_count == 2
    assert result.record.article_count == 2


async def test_empty_root(client: AsyncHttpClient) -> None:
    """Empty root category returns an empty expansion without error."""
    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = _members()
        expander = WikiCategoryExpander(max_depth=2)
        result = await expander.expand(CategoryRef(title="EmptyRoot"), client)

    assert result.record.article_count == 0
    assert result.child_refs == []


async def test_sub_categories_fetched_concurrently(
    client: AsyncHttpClient,
) -> None:
    """Same-level sub-categories are gathered concurrently (all called once)."""
    root_members = _members(
        articles=[],
        sub_categories=["Sub A", "Sub B", "Sub C"],
    )
    sub_response = _members(articles=[])

    with patch(
        "ladon_mimir.expanders._fetch_members", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = [
            root_members,
            sub_response,
            sub_response,
            sub_response,
        ]
        expander = WikiCategoryExpander(max_depth=1)
        await expander.expand(CategoryRef(title="Root"), client)

    # Root + 3 sub-cats = 4 total calls
    assert mock_fetch.call_count == 4
    called_titles = [call.args[0] for call in mock_fetch.call_args_list]
    assert set(called_titles) == {"Root", "Sub A", "Sub B", "Sub C"}
