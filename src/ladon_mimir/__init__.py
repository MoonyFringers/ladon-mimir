from importlib.metadata import PackageNotFoundError, version

from ladon import Expansion

from .expanders import WikiCategoryExpander
from .models import ArticleRecord, CategoryRecord, SubCategoryRecord
from .plugin import MimirPlugin
from .refs import ArticleRef, CategoryRef
from .sink import LeafUnavailableError, WikiArticleSink
from .source import WikiCategorySource
from .storage import export_parquet

try:
    __version__ = version("ladon-mimir")
except PackageNotFoundError:
    __version__ = "0.2.0"

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
    "export_parquet",
]
