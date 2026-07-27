"""Top‑level package for news‑pipeline."""
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "0.0.0"

from .config import settings  # re‑export for convenience