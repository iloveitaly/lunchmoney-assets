from structlog_config import configure_logger

from .cli import main
from .version import __version__

log = configure_logger()

__all__ = [
    "__version__",
    "main",
]
