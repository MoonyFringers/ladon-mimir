"""Tests for export_parquet."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from ladon_mimir.models import ArticleRecord, CategoryRecord
from ladon_mimir.repository import MimirRepository
from ladon_mimir.storage import export_parquet

_NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_CATEGORY = CategoryRecord(title="Mathematical finance", article_count=3)


def _make_article(page_id: int, title: str = "Test Article") -> ArticleRecord:
    return ArticleRecord(
        page_id=page_id,
        title=title,
        summary="Summary.",
        full_text="Full text.",
        categories=("Cat A",),
        last_modified=_NOW,
        word_count=2,
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
    )


def _populated_db(tmp_path: Path, page_ids: list[int]) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = str(tmp_path / "test.db")
    with MimirRepository(db) as repo:
        repo.start_run("Mathematical finance")
        for pid in page_ids:
            repo.save_article(_make_article(pid, f"Article {pid}"), _CATEGORY)
        repo.finish_run()
    return db


def test_export_parquet_returns_row_count(tmp_path: Path) -> None:
    db = _populated_db(tmp_path, [1, 2, 3])
    out = str(tmp_path / "out.parquet")
    assert export_parquet(db, out) == 3


def test_export_parquet_creates_file(tmp_path: Path) -> None:
    db = _populated_db(tmp_path, [10, 20])
    out = str(tmp_path / "out.parquet")
    export_parquet(db, out)
    assert Path(out).exists()
    assert Path(out).stat().st_size > 0


def test_export_parquet_empty_table(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.db")
    with MimirRepository(db) as repo:
        repo.start_run("Mathematical finance")
        repo.finish_run()
    out = str(tmp_path / "out.parquet")
    assert export_parquet(db, out) == 0


def test_export_parquet_content_readable(tmp_path: Path) -> None:
    db = _populated_db(tmp_path, [42])
    out = str(tmp_path / "out.parquet")
    export_parquet(db, out)

    rows = duckdb.sql(
        f"SELECT page_id, title FROM read_parquet('{out}')"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 42
    assert rows[0][1] == "Article 42"


def test_export_parquet_categories_json(tmp_path: Path) -> None:
    db = _populated_db(tmp_path, [7])
    out = str(tmp_path / "out.parquet")
    export_parquet(db, out)

    row = duckdb.sql(f"SELECT categories FROM read_parquet('{out}')").fetchone()
    assert row is not None
    cats = json.loads(row[0])
    assert cats == ["Cat A"]


def test_export_parquet_overwrites_existing(tmp_path: Path) -> None:
    db1 = _populated_db(tmp_path / "db1", [1, 2, 3])
    db2 = _populated_db(tmp_path / "db2", [10])
    out = str(tmp_path / "out.parquet")

    export_parquet(db1, out)
    assert export_parquet(db2, out) == 1

    rows = duckdb.sql(f"SELECT page_id FROM read_parquet('{out}')").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 10
