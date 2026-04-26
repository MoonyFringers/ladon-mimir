from datetime import datetime, timezone

from ladon_mimir.models import ArticleRecord, CategoryRecord, SubCategoryRecord
from ladon_mimir.refs import ArticleRef, CategoryRef


def test_article_record_immutable() -> None:
    record = ArticleRecord(
        page_id=1,
        title="Black–Scholes model",
        summary="A model of a financial market.",
        full_text="A model of a financial market containing derivative instruments.",
        categories=("Mathematical finance", "Options"),
        last_modified=datetime(2024, 1, 1, tzinfo=timezone.utc),
        word_count=9,
        url="https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model",
    )
    assert record.page_id == 1
    assert record.word_count == 9
    assert isinstance(record.categories, tuple)


def test_article_record_frozen() -> None:
    record = ArticleRecord(
        page_id=2,
        title="Test",
        summary="Summary.",
        full_text="Full text.",
        categories=(),
        last_modified=datetime(2024, 1, 1, tzinfo=timezone.utc),
        word_count=2,
        url="https://en.wikipedia.org/wiki/Test",
    )
    try:
        record.title = "mutated"  # type: ignore[misc]
        assert False, "should have raised"
    except Exception:
        pass


def test_category_record() -> None:
    record = CategoryRecord(title="Mathematical_finance", article_count=201)
    assert record.title == "Mathematical_finance"
    assert record.article_count == 201


def test_sub_category_record() -> None:
    record = SubCategoryRecord(title="Actuarial science")
    assert record.title == "Actuarial science"


def test_category_ref_default_url() -> None:
    ref = CategoryRef(title="Mathematical_finance")
    assert ref.url == ""


def test_category_ref_with_url() -> None:
    ref = CategoryRef(
        title="Mathematical_finance",
        url="https://en.wikipedia.org/wiki/Category:Mathematical_finance",
    )
    assert ref.url != ""


def test_article_ref() -> None:
    ref = ArticleRef(
        page_id=42,
        title="Itô calculus",
        url="https://en.wikipedia.org/wiki/It%C3%B4_calculus",
    )
    assert ref.page_id == 42
    assert ref.title == "Itô calculus"
