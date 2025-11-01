import sys
from datetime import datetime
import logging
import os
import gzip
import shutil
from logging.handlers import BaseRotatingHandler
from pathlib import Path

from utils import get_app_dir


class CompressedRotatingFileHandler(BaseRotatingHandler):
    """
    A rotating log file handler that compresses rotated files.

    This handler behaves like a standard rotating file handler, but when a
    rollover occurs, the old log file is compressed into a `.gz` archive.
    It also limits the number of backups retained.

    Attributes
    ----------
    maxBytes : int
        Maximum size in bytes before a rollover is triggered.
    backupCount : int
        Maximum number of compressed backup files to retain.
    log_dir : Path
        Directory where log files are stored.
    """

    def __init__(self, filename, mode="a", maxBytes=10 * 1024 * 1024,
                 backupCount=5, encoding=None, delay=False):
        """
        Initialize the handler and ensure the log directory exists.

        Parameters
        ----------
        filename : str or Path
            Path to the main log file.
        mode : str, optional
            File mode (default is "a").
        maxBytes : int, optional
            Maximum size in bytes before triggering a rollover.
        backupCount : int, optional
            Number of compressed backups to retain.
        encoding : str, optional
            Encoding for the log file.
        delay : bool, optional
            If True, file opening is deferred until the first write.
        """
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.log_dir = Path(filename).parent

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(filename, mode, encoding=encoding, delay=delay)

    def shouldRollover(self, record):
        """
        Determine whether the log file should be rotated.

        Checks if the size of the log file plus the next log message
        would exceed the `maxBytes` limit.

        Parameters
        ----------
        record : logging.LogRecord
            The log record about to be written.

        Returns
        -------
        bool
            True if rollover should occur, False otherwise.
        """
        if self.stream is None:
            self.stream = self._open()

        if self.maxBytes > 0:
            msg = f"{self.format(record)}\n"
            self.stream.seek(0, os.SEEK_END)
            if self.stream.tell() + len(msg.encode(self.encoding or "utf-8")) >= self.maxBytes:
                return True
        return False

    def doRollover(self):
        """
        Perform the rollover, compress the old file, and maintain only recent backups.

        The current log file is closed, compressed into `.gz`, and deleted.
        Then only the most recent `backupCount` compressed files are kept.
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        # Create timestamped filename
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        rotated_file = self.log_dir / f"{Path(self.baseFilename).name}.{ts}.gz"

        # Compress current file
        if os.path.exists(self.baseFilename):
            with open(self.baseFilename, "rb") as f_in, gzip.open(rotated_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(self.baseFilename)

        # Keep only the latest N compressed backups
        files = sorted(
            (f for f in self.log_dir.glob("*.gz") if f.is_file()),
            key=lambda f: f.stat().st_mtime
        )
        if len(files) > self.backupCount:
            for old_file in files[:-self.backupCount]:
                old_file.unlink()

        # Reopen new empty log file
        if not self.delay:
            self.stream = self._open()


def setup_logger(console,
                 logger_name="GliAAns-UI",
                 logfile=None,
                 level=logging.ERROR,
                 maxBytes=10 * 1024 * 1024,
                 backupCount=5):
    """
    Configure and return a logger with optional console output.

    Parameters
    ----------
    console : bool
        If True, also log messages to the console (stdout).
    logger_name : str, optional
        Name of the logger (default: "GliAAns-UI").
    logfile : str or Path, optional
        Path to the log file. If None, defaults to `~/.log/log.txt` inside
        the app directory.
    level : int, optional
        Logging level (default: logging.ERROR).
    maxBytes : int, optional
        Maximum log file size before rotation.
    backupCount : int, optional
        Number of compressed backups to retain.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    # Determine log directory under the application path
    app_dir = get_app_dir()
    log_dir = app_dir / ".log"
    log_dir.mkdir(parents=True, exist_ok=True)

    if logfile is None:
        logfile = log_dir / "log.txt"

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler with compression and rotation
    handler = CompressedRotatingFileHandler(
        logfile,
        maxBytes=maxBytes,
        backupCount=backupCount
    )
    file_formatter = logging.Formatter(
        "%(asctime)s\t%(levelname)s\t%(filename)s:%(lineno)d\t%(funcName)s\t%(message)s"
    )
    handler.setFormatter(file_formatter)
    logger.addHandler(handler)

    # Optional console handler for interactive debugging
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "%(levelname)s\t%(filename)s:%(lineno)d\t%(funcName)s\t%(message)s"
        )
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(logger_name="GliAAns-UI"):
    """
    Retrieve an existing logger instance by name.

    Parameters
    ----------
    logger_name : str, optional
        The logger name (default: "GliAAns-UI").

    Returns
    -------
    logging.Logger
        The requested logger instance.
    """
    return logging.getLogger(logger_name)


def set_log_level(level, logger_name="GliAAns-UI"):
    """
    Set the log level for an existing logger.

    Parameters
    ----------
    level : int
        Logging level (e.g., logging.DEBUG, logging.INFO).
    logger_name : str, optional
        Name of the logger (default: "GliAAns-UI").
    """
    logging.getLogger(logger_name).setLevel(level)
