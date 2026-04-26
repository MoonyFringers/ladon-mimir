"""MimirRepository — DuckDB-backed persistence for ladon-mimir.

Schema
------
``mimir_articles`` — one row per article, keyed on ``page_id`` (upsert).
``ladon_runs``     — one row per run, keyed on ``run_id``.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# Rationale: duckdb's Python wrapper is only partially typed; all three
# suppressions are confined to this file.
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Literal

import duckdb

from .models import ArticleRecord, CategoryRecord

RunStatus = Literal["running", "done", "failed"]

_CREATE_ARTICLES = """
CREATE TABLE IF NOT EXISTS mimir_articles (
    run_id        TEXT    NOT NULL,
    page_id       INTEGER NOT NULL,
    title         TEXT    NOT NULL,
    summary       TEXT    NOT NULL,
    full_text     TEXT    NOT NULL,
    categories    TEXT    NOT NULL,
    last_modified TIMESTAMPTZ NOT NULL,
    word_count    INTEGER NOT NULL,
    url           TEXT    NOT NULL,
    PRIMARY KEY (page_id)
)
"""

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS ladon_runs (
    run_id           TEXT PRIMARY KEY,
    category         TEXT        NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ,
    status           TEXT        NOT NULL,
    articles_fetched INTEGER     NOT NULL DEFAULT 0,
    articles_failed  INTEGER     NOT NULL DEFAULT 0
)
"""

_UPSERT_ARTICLE = """
INSERT INTO mimir_articles
    (run_id, page_id, title, summary, full_text,
     categories, last_modified, word_count, url)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (page_id) DO UPDATE SET
    run_id        = excluded.run_id,
    title         = excluded.title,
    summary       = excluded.summary,
    full_text     = excluded.full_text,
    categories    = excluded.categories,
    last_modified = excluded.last_modified,
    word_count    = excluded.word_count,
    url           = excluded.url
"""

_INSERT_RUN = """
INSERT INTO ladon_runs (run_id, category, started_at, status)
VALUES (?, ?, ?, 'running')
"""

_UPDATE_RUN = """
UPDATE ladon_runs
SET status           = ?,
    finished_at      = ?,
    articles_fetched = ?,
    articles_failed  = ?
WHERE run_id = ?
"""

_GET_PAGE_IDS = """
SELECT page_id FROM mimir_articles
"""


class MimirRepository:
    """DuckDB-backed persistence for the ladon-mimir adapter.

    Handles article upserts, run lifecycle tracking, and resume support
    via ``get_existing_page_ids``.

    Args:
        db_path: Path to the DuckDB file, or ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str) -> None:
        self._conn: duckdb.DuckDBPyConnection = duckdb.connect(db_path)
        self._conn.execute(_CREATE_ARTICLES)
        self._conn.execute(_CREATE_RUNS)
        self._run_id: str = ""
        self._articles_fetched: int = 0
        self._articles_failed: int = 0

    def start_run(self, category: str) -> str:
        """Start a new run for *category*. Returns the generated run_id."""
        run_id = str(uuid.uuid4())
        self._run_id = run_id
        self._articles_fetched = 0
        self._articles_failed = 0
        self._conn.execute(
            _INSERT_RUN,
            [run_id, category, datetime.now(tz=timezone.utc)],
        )
        return run_id

    def finish_run(self, status: RunStatus = "done") -> None:
        """Mark the current run as finished with *status*."""
        self._conn.execute(
            _UPDATE_RUN,
            [
                status,
                datetime.now(tz=timezone.utc),
                self._articles_fetched,
                self._articles_failed,
                self._run_id,
            ],
        )

    def get_existing_page_ids(self) -> frozenset[int]:
        """Return all page IDs already stored in the database."""
        rows = self._conn.execute(_GET_PAGE_IDS).fetchall()
        return frozenset(int(row[0]) for row in rows)

    def save_article(
        self, record: ArticleRecord, _parent: CategoryRecord  # noqa: ARG002
    ) -> None:
        """Upsert one ``ArticleRecord`` into ``mimir_articles``.

        *_parent* is accepted for runner-protocol compatibility but not stored;
        article categories are taken from ``record.categories``.
        """
        self._conn.execute(
            _UPSERT_ARTICLE,
            [
                self._run_id,
                record.page_id,
                record.title,
                record.summary,
                record.full_text,
                json.dumps(list(record.categories)),
                record.last_modified,
                record.word_count,
                record.url,
            ],
        )
        self._articles_fetched += 1

    def record_failure(self) -> None:
        """Increment the failed article counter for the current run."""
        self._articles_failed += 1

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def __enter__(self) -> MimirRepository:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
