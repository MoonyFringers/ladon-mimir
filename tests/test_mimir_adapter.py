"""Tests for MimirMCPAdapter — data-plane tools and resources."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, cast

import duckdb
import pytest

from ladon_mimir.mcp import MimirMCPAdapter

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
_RUN_ID = "run-mcp-test"


def _make_db(tmp_path: pytest.TempPathFactory) -> str:  # type: ignore[type-arg]
    db_path = str(tmp_path / "mimir.db")  # type: ignore[operator]
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE mimir_articles (
            run_id TEXT NOT NULL, page_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL, summary TEXT NOT NULL,
            full_text TEXT NOT NULL, categories TEXT NOT NULL,
            last_modified TIMESTAMPTZ NOT NULL,
            word_count INTEGER NOT NULL, url TEXT NOT NULL
        )
    """)
    articles = [
        (
            1,
            "Black–Scholes model",
            "BSM is a model for option pricing.",
            "The Black–Scholes–Merton model prices European options.",
            json.dumps(["Mathematical finance", "Options"]),
            1200,
            "https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model",
        ),
        (
            2,
            "Monte Carlo method",
            "A computational technique using random sampling.",
            "Monte Carlo methods rely on repeated random sampling.",
            json.dumps(["Computational methods", "Statistics"]),
            2300,
            "https://en.wikipedia.org/wiki/Monte_Carlo_method",
        ),
        (
            3,
            "Stochastic calculus",
            "Branch of mathematics operating on stochastic processes.",
            "Stochastic calculus extends integration to stochastic processes.",
            json.dumps(["Mathematics"]),
            900,
            "https://en.wikipedia.org/wiki/Stochastic_calculus",
        ),
    ]
    for page_id, title, summary, full_text, cats, wc, url in articles:
        con.execute(
            "INSERT INTO mimir_articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [_RUN_ID, page_id, title, summary, full_text, cats, _NOW, wc, url],
        )
    con.close()
    return db_path


@pytest.fixture()
def adapter(tmp_path: pytest.TempPathFactory) -> MimirMCPAdapter:  # type: ignore[type-arg]
    return MimirMCPAdapter(_make_db(tmp_path))


class TestMimirAdapterMetadata:
    def test_adapter_name(self, adapter: MimirMCPAdapter) -> None:
        assert adapter.adapter_name == "mimir"

    def test_mcp_tools_count(self, adapter: MimirMCPAdapter) -> None:
        assert len(adapter.mcp_tools()) == 2

    def test_mcp_resources_count(self, adapter: MimirMCPAdapter) -> None:
        resources = adapter.mcp_resources()
        assert len(resources) == 1
        uri_template, _ = resources[0]
        assert uri_template == "ladon://mimir/articles/{page_id}"


class TestMimirArticleSearch:
    def _search(
        self, adapter: MimirMCPAdapter, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        search_fn = adapter.mcp_tools()[0]
        return cast(list[dict[str, Any]], search_fn(query=query, limit=limit))  # type: ignore[call-arg]

    def test_matches_title(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "Black")
        assert len(results) == 1
        assert results[0]["title"] == "Black–Scholes model"

    def test_matches_summary(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "random sampling")
        assert any(r["title"] == "Monte Carlo method" for r in results)

    def test_matches_full_text(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "stochastic processes")
        titles = [r["title"] for r in results]
        assert "Stochastic calculus" in titles

    def test_case_insensitive(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "MONTE")
        assert len(results) == 1
        assert results[0]["title"] == "Monte Carlo method"

    def test_categories_deserialized_as_list(
        self, adapter: MimirMCPAdapter
    ) -> None:
        results = self._search(adapter, "Black")
        assert isinstance(results[0]["categories"], list)
        assert "Mathematical finance" in results[0]["categories"]

    def test_limit_respected(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "a", limit=1)
        assert len(results) <= 1

    def test_no_match_returns_empty(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "xyzzy_no_match_at_all")
        assert results == []

    def test_ordered_by_word_count_desc(self, adapter: MimirMCPAdapter) -> None:
        results = self._search(adapter, "s")
        word_counts = [r["word_count"] for r in results]
        assert word_counts == sorted(word_counts, reverse=True)

    def test_db_error_returns_error_dict(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:  # type: ignore[type-arg]
        empty_db = str(tmp_path / "empty.db")  # type: ignore[operator]
        duckdb.connect(empty_db).close()
        adapter = MimirMCPAdapter(empty_db)
        search_fn = adapter.mcp_tools()[0]
        result = cast(list[dict[str, Any]], search_fn(query="test"))  # type: ignore[call-arg]
        assert len(result) == 1
        assert "error" in result[0]


class TestMimirCorpusStats:
    def _stats(self, adapter: MimirMCPAdapter) -> dict[str, Any]:
        stats_fn = adapter.mcp_tools()[1]
        return cast(dict[str, Any], stats_fn())  # type: ignore[call-arg]

    def test_article_count(self, adapter: MimirMCPAdapter) -> None:
        stats = self._stats(adapter)
        assert stats["article_count"] == 3

    def test_total_words(self, adapter: MimirMCPAdapter) -> None:
        stats = self._stats(adapter)
        assert stats["total_words"] == 1200 + 2300 + 900

    def test_date_range_present(self, adapter: MimirMCPAdapter) -> None:
        stats = self._stats(adapter)
        assert "oldest_article" in stats
        assert "newest_article" in stats

    def test_empty_db_returns_zero_count(self, tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
        empty_db = str(tmp_path / "empty.db")  # type: ignore[operator]
        con = duckdb.connect(empty_db)
        con.execute("""
            CREATE TABLE mimir_articles (
                run_id TEXT NOT NULL, page_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL, summary TEXT NOT NULL,
                full_text TEXT NOT NULL, categories TEXT NOT NULL,
                last_modified TIMESTAMPTZ NOT NULL,
                word_count INTEGER NOT NULL, url TEXT NOT NULL
            )
        """)
        con.close()
        empty_adapter = MimirMCPAdapter(empty_db)
        stats_fn = empty_adapter.mcp_tools()[1]
        stats = cast(dict[str, Any], stats_fn())  # type: ignore[call-arg]
        assert stats["article_count"] == 0

    def test_db_error_returns_error_dict(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:  # type: ignore[type-arg]
        empty_db = str(tmp_path / "empty.db")  # type: ignore[operator]
        duckdb.connect(empty_db).close()
        empty_adapter = MimirMCPAdapter(empty_db)
        stats_fn = empty_adapter.mcp_tools()[1]
        result = cast(dict[str, Any], stats_fn())  # type: ignore[call-arg]
        assert "error" in result


class TestMimirArticleResource:
    def _resource(self, adapter: MimirMCPAdapter, page_id: int) -> str:
        _, resource_fn = adapter.mcp_resources()[0]
        return resource_fn(page_id=page_id)  # type: ignore[call-arg]

    def test_returns_markdown(self, adapter: MimirMCPAdapter) -> None:
        content = self._resource(adapter, 1)
        assert "# Black–Scholes model" in content
        assert "## Summary" in content
        assert "## Full Text" in content

    def test_includes_categories(self, adapter: MimirMCPAdapter) -> None:
        content = self._resource(adapter, 1)
        assert "Mathematical finance" in content
        assert "Options" in content

    def test_missing_page_id(self, adapter: MimirMCPAdapter) -> None:
        content = self._resource(adapter, 999)
        assert "not found" in content
