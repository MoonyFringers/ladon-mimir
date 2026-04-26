try:
    from importlib.metadata import version, PackageNotFoundError

    __version__ = version("ladon-mimir")
except PackageNotFoundError:
    __version__ = "0.1.0"
