from pathlib import Path

from app.logger import Logger


def test_logger_writes_info_warning_and_error(tmp_path: Path):
    log_file = tmp_path / "logs" / "calculator.log"

    Logger.configure(log_file)
    Logger.info("Calculation performed: Addition(2, 3) = 5")
    Logger.warning("History could not be loaded")
    Logger.error("Calculation failed")

    contents = log_file.read_text(encoding="utf-8")
    assert "INFO - Calculation performed: Addition(2, 3) = 5" in contents
    assert "WARNING - History could not be loaded" in contents
    assert "ERROR - Calculation failed" in contents


def test_logger_uses_configured_encoding(tmp_path: Path):
    log_file = tmp_path / "calculator.log"

    Logger.configure(log_file, encoding="utf-16")
    Logger.info("Configured encoding")

    assert "Configured encoding" in log_file.read_text(encoding="utf-16")
