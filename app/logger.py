import logging
from pathlib import Path
from typing import Any


class Logger:
    """Configure and expose the calculator's application logger."""

    _logger = logging.getLogger("calculator")

    @classmethod
    def configure(cls, log_file: Path, encoding: str = "utf-8") -> None:
        """Write calculator log records to the configured file."""
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        for handler in cls._logger.handlers[:]:
            cls._logger.removeHandler(handler)
            handler.close()

        file_handler = logging.FileHandler(log_path, encoding=encoding)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))

        cls._logger.setLevel(logging.INFO)
        cls._logger.addHandler(file_handler)
        cls._logger.propagate = True
        cls.info("Logging initialized at: %s", log_path.resolve())

    @classmethod
    def info(cls, message: str, *args: Any) -> None:
        cls._logger.info(message, *args)

    @classmethod
    def warning(cls, message: str, *args: Any) -> None:
        cls._logger.warning(message, *args)

    @classmethod
    def error(cls, message: str, *args: Any) -> None:
        cls._logger.error(message, *args)