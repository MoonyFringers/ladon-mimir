"""MimirMCPAdapter — registers ladon-mimir data-plane tools with ladon-nous."""

from __future__ import annotations

import json
from typing import Any, Callable

import duckdb
from ladon.mcp import LadonMCPAdapter


class MimirMCPAdapter(LadonMCPAdapter):
    """Exposes mimir_articles to ladon-nous via MCP tools.

    Registered via the ``ladon.mcp`` entry-point group — installing
    ladon-mimir alongside ladon-nous is sufficient; no extra configuration.
    """

    @property
    def adapter_name(self) -> str:
        return "mimir"

    def mcp_tools(self) -> list[Callable[..., object]]:
        db_path = self.db_path

        def mimir_article_search(
            query: str,
            limit: int = 10,
        ) -> list[dict[str, Any]]:
            """Search crawled Wikipedia articles by keyword.

            Matches against title, summary, and full text (case-insensitive).
            Returns up to `limit` results ordered by word count descending.
            Each result includes: page_id, title, summary, categories,
            word_count, url.
            """
            sql = """
                SELECT page_id, title, summary, categories, word_count, url
                FROM mimir_articles
                WHERE lower(title)     LIKE lower(?)
                   OR lower(summary)   LIKE lower(?)
                   OR lower(full_text) LIKE lower(?)
                ORDER BY word_count DESC
                LIMIT ?
            """
            pattern = f"%{query}%"
            try:
                with duckdb.connect(db_path, read_only=True) as con:
                    rows = con.execute(
                        sql, [pattern, pattern, pattern, limit]
                    ).fetchall()
            except duckdb.Error as exc:
                return [{"error": f"Database error: {exc}"}]

            return [
                {
                    "page_id": r[0],
                    "title": r[1],
                    "summary": r[2],
                    "categories": json.loads(r[3]),
                    "word_count": r[4],
                    "url": r[5],
                }
                for r in rows
            ]

        def mimir_corpus_stats() -> dict[str, Any]:
            """Return summary statistics for the stored Wikipedia corpus.

            Includes: total article count, total word count, and the date
            range of last_modified timestamps.
            """
            sql_summary = """
                SELECT
                    count(*)        AS article_count,
                    sum(word_count) AS total_words,
                    min(last_modified)::TEXT AS oldest,
                    max(last_modified)::TEXT AS newest
                FROM mimir_articles
            """
            try:
                with duckdb.connect(db_path, read_only=True) as con:
                    row = con.execute(sql_summary).fetchone()
            except duckdb.Error as exc:
                return {"error": f"Database error: {exc}"}

            assert row is not None  # COUNT(*) always returns exactly one row
            if row[0] == 0:
                return {"article_count": 0, "message": "No articles stored."}

            return {
                "article_count": row[0],
                "total_words": row[1],
                "oldest_article": row[2],
                "newest_article": row[3],
            }

        return [mimir_article_search, mimir_corpus_stats]

    def mcp_resources(
        self,
    ) -> list[tuple[str, Callable[..., object]]]:
        db_path = self.db_path

        def article_resource(page_id: int) -> str:
            """Full Markdown content of a single crawled Wikipedia article."""
            sql = """
                SELECT title, summary, full_text, categories,
                       word_count, url, last_modified
                FROM mimir_articles
                WHERE page_id = ?
            """
            try:
                with duckdb.connect(db_path, read_only=True) as con:
                    row = con.execute(sql, [page_id]).fetchone()
            except duckdb.Error as exc:
                return f"Error fetching article {page_id}: {exc}"

            if row is None:
                return f"Article {page_id} not found."

            cats = json.loads(row[3])
            return (
                f"# {row[0]}\n\n"
                f"**Categories**: {', '.join(cats)}\n"
                f"**Word count**: {row[4]}\n"
                f"**Last modified**: {row[6]}\n"
                f"**URL**: {row[5]}\n\n"
                f"## Summary\n{row[1]}\n\n"
                f"## Full Text\n{row[2]}"
            )

        return [("ladon://mimir/articles/{page_id}", article_resource)]
