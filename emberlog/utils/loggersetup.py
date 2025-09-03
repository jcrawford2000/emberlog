import logging
import logging.config

from pythonjsonlogger import jsonlogger

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {
            "format": "%(asctime)s | %(levelname)-7s | %(logger_id)s | %(class_method)s - %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(class_method)s %(logger_id)s %(message)s",
        },
    },
    "filters": {
        "class_method": {"()": "emberlog.utils.logging_filters.ClassMethodFilter"},
        "logger_id": {"()": "emberlog.utils.logging_filters.LoggerIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "dev",
            "filters": ["class_method", "logger_id"],
        },
        "file_app": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "filename": "logs/app.log",
            "formatter": "json",
            "filters": ["class_method", "logger_id"],
        },
    },
    "loggers": {
        # Per-module control
        "emberlog.app": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.queue": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.state": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.transcriber": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.watch": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.worker": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.cleaning": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        "emberlog.io": {
            "level": "DEBUG",
            "handlers": ["console", "file_app"],
            "propagate": False,
        },
        # Fallback
        "": {"level": "WARNING", "handlers": ["console"]},
    },
}


def configure_logging():
    logging.config.dictConfig(LOGGING)
