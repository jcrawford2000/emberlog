"""Logger Setup"""

from __future__ import annotations

import sys

from loguru import logger as _logger


def get_logger(name: str = "Unknown", level: str = "INFO"):
    """Gets a logger and sets log level"""

    if not getattr(get_logger, "_configured", False):
        _logger.remove()
        _logger.add(
            sys.stderr,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level.icon} {level: <8}</level> | "
                "<cyan>{module}.{function}</cyan>:"
                "<cyan>{line}</cyan> - <level>{message}</level>"
            ),
            level=level.upper(),
        )
        setattr(get_logger, "_configured", True)
    return _logger
