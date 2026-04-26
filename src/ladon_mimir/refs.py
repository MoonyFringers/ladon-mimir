from dataclasses import dataclass, field


@dataclass(frozen=True)
class CategoryRef:
    title: str
    url: str = field(default="")


@dataclass(frozen=True)
class ArticleRef:
    page_id: int
    title: str
    url: str
