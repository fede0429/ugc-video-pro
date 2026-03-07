"""
utils/logger.py
===============
Centralized logging configuration for UGC Video Pro.

Provides:
    - setup_logger(): Configure root logger (call once from main.py)
    - get_logger(name): Get a named logger for any module

Log format:
    [timestamp] [level] [module] message

Supports both console and optional file logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


# Custom formatter with colors for terminal output
class ColorFormatter(logging.Formatter):
    """Colored terminal output formatter."""

    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    force: bool = False,
) -> logging.Logger:
    """
    Configure the root logger for UGC Video Pro.
    
    Call this once from main.py before any other imports.
    
    Args:
        level: Log level string: DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_file: Optional path to write logs to file (in addition to console)
        force: Force reconfiguration even if already configured
    
    Returns:
        Configured root logger
    """
    # Parse level string
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()

    if root_logger.handlers and not force:
        return root_logger

    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (with colors if terminal, plain if redirected)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if sys.stdout.isatty():
        fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        formatter = ColorFormatter(fmt=fmt, datefmt="%H:%M:%S")
    else:
        fmt = "%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s"
        formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Suppress overly verbose third-party loggers
    for noisy_logger in [
        "httpx",
        "httpcore",
        "asyncio",
        "telegram.ext",
        "telegram.bot",
        "urllib3",
        "google.auth",
        "googleapiclient",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for a module.
    
    Usage:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Starting...")
    
    Args:
        name: Logger name, typically __name__ of the calling module
    
    Returns:
        Named logger instance
    """
    return logging.getLogger(name)
