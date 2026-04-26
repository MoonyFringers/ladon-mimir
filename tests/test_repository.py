"""Tests for MimirRepository (DuckDB-backed persistence)."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from ladon_mimir.models import ArticleRecord, CategoryRecord
from ladon_mimir.repository import MimirRepository

_NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

_CATEGORY = CategoryRecord(title="Mathematical finance", article_count=5)


def _make_article(page_id: int, title: str = "Test Article") -> ArticleRecord:
    return ArticleRecord(
        page_id=page_id,
        title=title,
        summary="A brief summary.",
        full_text="Full text content here.",
        categories=("Cat A", "Cat B"),
        last_modified=_NOW,
        word_count=4,
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
    )


@pytest.fixture
def repo() -> MimirRepository:
    return MimirRepository(":memory:")


def test_init_creates_tables(repo: MimirRepository) -> None:
    rows = repo._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "mimir_articles" in names
    assert "ladon_runs" in names


def test_start_run_returns_uuid(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    assert len(run_id) == 36
    assert run_id.count("-") == 4


def test_start_run_inserts_row(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    row = repo._conn.execute(
        "SELECT status, category FROM ladon_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == "running"
    assert row[1] == "Mathematical finance"


def test_finish_run_updates_status(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    repo.finish_run("done")
    row = repo._conn.execute(
        "SELECT status, finished_at FROM ladon_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == "done"
    assert row[1] is not None


def test_finish_run_failed_status(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    repo.finish_run("failed")
    row = repo._conn.execute(
        "SELECT status FROM ladon_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == "failed"


def test_save_article_inserts_row(repo: MimirRepository) -> None:
    repo.start_run("Mathematical finance")
    article = _make_article(42, "Black–Scholes")
    repo.save_article(article, _CATEGORY)

    row = repo._conn.execute(
        "SELECT title, word_count FROM mimir_articles WHERE page_id = 42"
    ).fetchone()
    assert row is not None
    assert row[0] == "Black–Scholes"
    assert row[1] == 4


def test_save_article_upsert(repo: MimirRepository) -> None:
    repo.start_run("Mathematical finance")
    repo.save_article(_make_article(42, "Old Title"), _CATEGORY)
    repo.save_article(_make_article(42, "New Title"), _CATEGORY)

    rows = repo._conn.execute(
        "SELECT title FROM mimir_articles WHERE page_id = 42"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "New Title"


def test_get_existing_page_ids_empty(repo: MimirRepository) -> None:
    assert repo.get_existing_page_ids() == frozenset()


def test_get_existing_page_ids_after_inserts(repo: MimirRepository) -> None:
    repo.start_run("Mathematical finance")
    repo.save_article(_make_article(10), _CATEGORY)
    repo.save_article(_make_article(20), _CATEGORY)
    repo.save_article(_make_article(30), _CATEGORY)

    ids = repo.get_existing_page_ids()
    assert ids == frozenset({10, 20, 30})


def test_articles_fetched_counter(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    repo.save_article(_make_article(1), _CATEGORY)
    repo.save_article(_make_article(2), _CATEGORY)
    repo.finish_run()

    row = repo._conn.execute(
        "SELECT articles_fetched FROM ladon_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_record_failure_counter(repo: MimirRepository) -> None:
    run_id = repo.start_run("Mathematical finance")
    repo.record_failure()
    repo.record_failure()
    repo.finish_run()

    row = repo._conn.execute(
        "SELECT articles_failed FROM ladon_runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == 2


def test_context_manager_closes(repo: MimirRepository) -> None:
    with MimirRepository(":memory:") as r:
        r.start_run("Mathematical finance")
        r.save_article(_make_article(99), _CATEGORY)
    # connection should be closed; further queries raise
    with pytest.raises(duckdb.ConnectionException):
        r._conn.execute("SELECT 1")


def test_persistence_across_runs(tmp_path: pytest.TempPathFactory) -> None:
    db = str(tmp_path / "test.db")  # type: ignore[operator]

    with MimirRepository(db) as r1:
        r1.start_run("Mathematical finance")
        r1.save_article(_make_article(10), _CATEGORY)
        r1.save_article(_make_article(20), _CATEGORY)
        r1.finish_run()

    # second instance against the same file must see both articles
    with MimirRepository(db) as r2:
        ids = r2.get_existing_page_ids()

    assert ids == frozenset({10, 20})
