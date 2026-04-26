from importlib.metadata import PackageNotFoundError, version

from .expanders import Expansion, WikiCategoryExpander
from .models import ArticleRecord, CategoryRecord, SubCategoryRecord
from .plugin import MimirPlugin
from .refs import ArticleRef, CategoryRef
from .sink import LeafUnavailableError, WikiArticleSink
from .source import WikiCategorySource

try:
    __version__ = version("ladon-mimir")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "ArticleRecord",
    "ArticleRef",
    "CategoryRecord",
    "CategoryRef",
    "Expansion",
    "LeafUnavailableError",
    "MimirPlugin",
    "SubCategoryRecord",
    "WikiArticleSink",
    "WikiCategoryExpander",
    "WikiCategorySource",
]
