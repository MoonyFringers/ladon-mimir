"""Tests for the ladon-mimir CLI (argument parsing + dry-run path)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from ladon_mimir.cli import (
    _build_parser,
    _non_negative_int,
    _parquet_path,
    _positive_int,
    _run,
)

# ---------------------------------------------------------------------------
# _parquet_path
# ---------------------------------------------------------------------------


def test_parquet_path_replaces_extension() -> None:
    assert _parquet_path("mimir.db") == "mimir.parquet"


def test_parquet_path_absolute() -> None:
    assert (
        _parquet_path("/data/output/mimir.db") == "/data/output/mimir.parquet"
    )


def test_parquet_path_no_extension() -> None:
    assert _parquet_path("mimir") == "mimir.parquet"


# ---------------------------------------------------------------------------
# _positive_int / _non_negative_int validators
# ---------------------------------------------------------------------------


def test_positive_int_valid() -> None:
    validator = _positive_int("--concurrency")
    assert validator("5") == 5  # type: ignore[operator]


def test_positive_int_rejects_zero() -> None:
    validator = _positive_int("--concurrency")
    with pytest.raises(argparse.ArgumentTypeError, match="--concurrency"):
        validator("0")  # type: ignore[operator]


def test_positive_int_rejects_negative() -> None:
    validator = _positive_int("--concurrency")
    with pytest.raises(argparse.ArgumentTypeError):
        validator("-1")  # type: ignore[operator]


def test_positive_int_rejects_non_numeric() -> None:
    validator = _positive_int("--concurrency")
    with pytest.raises(argparse.ArgumentTypeError):
        validator("abc")  # type: ignore[operator]


def test_non_negative_int_valid_zero() -> None:
    validator = _non_negative_int("--limit")
    assert validator("0") == 0  # type: ignore[operator]


def test_non_negative_int_valid_positive() -> None:
    validator = _non_negative_int("--limit")
    assert validator("100") == 100  # type: ignore[operator]


def test_non_negative_int_rejects_negative() -> None:
    validator = _non_negative_int("--limit")
    with pytest.raises(argparse.ArgumentTypeError, match="--limit"):
        validator("-1")  # type: ignore[operator]


# ---------------------------------------------------------------------------
# _build_parser — argument defaults and types
# ---------------------------------------------------------------------------


def test_parser_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--category", "Mathematical finance"])
    assert args.category == "Mathematical finance"
    assert args.out == "mimir.db"
    assert args.concurrency == 10
    assert args.depth == 2
    assert args.limit == 0
    assert args.exclude_categories == []
    assert args.sync is False
    assert args.dry_run is False
    assert args.verbose is False


def test_parser_all_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--category",
            "Finance",
            "--out",
            "fin.db",
            "--concurrency",
            "5",
            "--depth",
            "3",
            "--limit",
            "100",
            "--exclude-category",
            "Stubs",
            "--exclude-category",
            "Disambiguation",
            "--sync",
            "--dry-run",
            "--verbose",
        ]
    )
    assert args.out == "fin.db"
    assert args.concurrency == 5
    assert args.depth == 3
    assert args.limit == 100
    assert args.exclude_categories == ["Stubs", "Disambiguation"]
    assert args.sync is True
    assert args.dry_run is True
    assert args.verbose is True


def test_parser_category_required() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ---------------------------------------------------------------------------
# _run — dry-run path (no HTTP, no real DB crawl)
# ---------------------------------------------------------------------------


async def test_dry_run_no_crawl(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / "test.db")
    # Patch _crawl to ensure it's never called
    with patch("ladon_mimir.cli._crawl") as mock_crawl:
        await _run(
            category="Mathematical finance",
            db_path=db,
            concurrency=10,
            depth=2,
            limit=0,
            exclude_categories=[],
            sync=False,
            dry_run=True,
        )
        mock_crawl.assert_not_called()

    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "Mathematical finance" in out


async def test_dry_run_shows_sync_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / "test.db")
    with patch("ladon_mimir.cli._crawl"):
        await _run(
            category="Mathematical finance",
            db_path=db,
            concurrency=10,
            depth=2,
            limit=0,
            exclude_categories=[],
            sync=True,
            dry_run=True,
        )

    out = capsys.readouterr().out
    assert ".parquet" in out


async def test_dry_run_shows_excludes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / "test.db")
    with patch("ladon_mimir.cli._crawl"):
        await _run(
            category="Mathematical finance",
            db_path=db,
            concurrency=10,
            depth=2,
            limit=0,
            exclude_categories=["Stubs", "Templates"],
            sync=False,
            dry_run=True,
        )

    out = capsys.readouterr().out
    assert "Stubs" in out
    assert "Templates" in out
