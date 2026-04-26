from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleRecord:
    page_id: int
    title: str
    summary: str
    full_text: str
    categories: tuple[str, ...]
    last_modified: datetime
    word_count: int
    url: str


@dataclass(frozen=True)
class CategoryRecord:
    title: str
    article_count: int


@dataclass(frozen=True)
class SubCategoryRecord:
    title: str
