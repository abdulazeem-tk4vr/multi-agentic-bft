"""Aegean protocol logging: file output under project ``logs/`` by default."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
_LOGGER_NAMESPACE = "aegean"

_lock = threading.Lock()


def default_log_path(log_dir: Path | None = None, filename: str = "aegean.log") -> Path:
    return (log_dir or DEFAULT_LOG_DIR) / filename


def _existing_file_handler_path(path: Path) -> bool:
    resolved = str(path.resolve())
    root = logging.getLogger(_LOGGER_NAMESPACE)
    for h in root.handlers:
        if isinstance(h, logging.FileHandler) and hasattr(h, "baseFilename"):
            if str(Path(h.baseFilename).resolve()) == resolved:
                return True
    return False


def configure_aegean_file_logging(
    log_dir: Path | None = None,
    *,
    level: int = logging.INFO,
    filename: str = "aegean.log",
) -> Path:
    """Attach a file handler for ``path`` under the ``aegean`` logger (no duplicate same path)."""
    path = default_log_path(log_dir, filename)
    log_dir_path = path.parent
    with _lock:
        log_dir_path.mkdir(parents=True, exist_ok=True)
        root = logging.getLogger(_LOGGER_NAMESPACE)
        if _existing_file_handler_path(path):
            return path
        prev = root.level
        root.setLevel(level if prev in (logging.NOTSET, 0) else min(prev, level))
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(fh)
    return path


def get_aegean_logger(name: str) -> logging.Logger:
    """Child logger under ``aegean.*`` (inherits handlers from ``aegean`` if configured)."""
    if name == _LOGGER_NAMESPACE or name.startswith(f"{_LOGGER_NAMESPACE}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")


def aegean_log(
    level: int,
    msg: str,
    *args: object,
    logger_name: str = "aegean",
    **kwargs: object,
) -> None:
    """Log a message on the named Aegean logger (configure file logging separately when desired)."""
    logging.getLogger(logger_name).log(level, msg, *args, **kwargs)
