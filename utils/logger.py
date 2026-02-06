"""
File-based logging for Hands-Free Anki addon.
Logs are saved to detect crashes and debug issues.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Module-level logger instance
_logger = None
_log_file_path = None


def get_log_path() -> Path:
    """Get the path to the log file."""
    addon_dir = Path(__file__).parent.parent
    logs_dir = addon_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir / "hands_free.log"


def get_crash_log_path() -> Path:
    """Get the path to the crash log file."""
    addon_dir = Path(__file__).parent.parent
    logs_dir = addon_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir / "crash.log"


def setup_logger() -> logging.Logger:
    """
    Set up and return the file logger.
    Uses rotating file handler to prevent log files from growing too large.
    """
    global _logger, _log_file_path

    if _logger is not None:
        return _logger

    _log_file_path = get_log_path()

    # Create logger
    _logger = logging.getLogger("hands_free_anki")
    _logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    _logger.handlers.clear()

    # Create rotating file handler (max 5MB, keep 3 backups)
    file_handler = RotatingFileHandler(
        _log_file_path,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Create console handler for important messages
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '[Hands-Free %(levelname)s] %(message)s'
    )

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    # Add handlers
    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)

    # Log startup
    _logger.info("=" * 60)
    _logger.info("Hands-Free Anki logger initialized")
    _logger.info(f"Log file: {_log_file_path}")
    _logger.info("=" * 60)

    return _logger


def get_logger() -> logging.Logger:
    """Get the logger instance, initializing if necessary."""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def log_exception(exc: Exception, context: str = ""):
    """
    Log an exception with full traceback to both log file and crash log.
    """
    import traceback

    logger = get_logger()

    # Format the exception
    exc_text = "".join(traceback.format_exception(
        type(exc), exc, exc.__traceback__))

    # Log to main log
    logger.error(f"EXCEPTION in {context}: {exc}")
    logger.error(f"Traceback:\n{exc_text}")

    # Also append to crash log for easy access
    crash_log_path = get_crash_log_path()
    try:
        with open(crash_log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"CRASH at {datetime.now().isoformat()}\n")
            f.write(f"Context: {context}\n")
            f.write("=" * 60 + "\n")
            f.write(exc_text)
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to write to crash log: {e}")


def log_session_start():
    """Log the start of a hands-free session."""
    logger = get_logger()
    logger.info("-" * 40)
    logger.info("HANDS-FREE SESSION STARTED")
    logger.info("-" * 40)


def log_session_end():
    """Log the end of a hands-free session."""
    logger = get_logger()
    logger.info("-" * 40)
    logger.info("HANDS-FREE SESSION ENDED")
    logger.info("-" * 40)


def log_card_processing(card_id: int, action: str, details: str = ""):
    """Log card processing events."""
    logger = get_logger()
    msg = f"Card {card_id}: {action}"
    if details:
        msg += f" - {details}"
    logger.info(msg)


def log_tts(message: str):
    """Log TTS-related events."""
    get_logger().debug(f"[TTS] {message}")


def log_stt(message: str):
    """Log STT-related events."""
    get_logger().debug(f"[STT] {message}")


def log_scoring(message: str):
    """Log scoring-related events."""
    get_logger().debug(f"[SCORING] {message}")


def log_error(message: str):
    """Log an error message."""
    get_logger().error(message)


def log_warning(message: str):
    """Log a warning message."""
    get_logger().warning(message)


def log_info(message: str):
    """Log an info message."""
    get_logger().info(message)


def log_debug(message: str):
    """Log a debug message."""
    get_logger().debug(message)


# Install global exception handler for uncaught exceptions
def _global_exception_handler(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions by logging them."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger()
    logger.critical("UNCAUGHT EXCEPTION", exc_info=(
        exc_type, exc_value, exc_traceback))

    # Also write to crash log
    import traceback
    exc_text = "".join(traceback.format_exception(
        exc_type, exc_value, exc_traceback))
    crash_log_path = get_crash_log_path()
    try:
        with open(crash_log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"UNCAUGHT EXCEPTION at {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n")
            f.write(exc_text)
            f.write("\n")
    except:
        pass

    # Call the original exception handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def install_exception_handler():
    """Install the global exception handler."""
    sys.excepthook = _global_exception_handler
    get_logger().info("Global exception handler installed")
