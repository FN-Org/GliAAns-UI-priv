import sys
from datetime import datetime
import logging
import os
import gzip
import shutil
from logging.handlers import BaseRotatingHandler
from pathlib import Path

from utils import resource_path, get_app_dir


class CompressedRotatingFileHandler(BaseRotatingHandler):
    def __init__(self, filename, mode="a", maxBytes=10*1024*1024,
                 backupCount=5, encoding=None, delay=False):
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.log_dir = Path(filename).parent

        # crea la cartella .log se non esiste
        self.log_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(filename, mode, encoding=encoding, delay=delay)

    def shouldRollover(self, record):
        """Decide se ruotare in base alla dimensione del file."""
        if self.stream is None:  # file non aperto
            self.stream = self._open()

        if self.maxBytes > 0:
            msg = f"{self.format(record)}\n"
            self.stream.seek(0, os.SEEK_END)
            if self.stream.tell() + len(msg.encode(self.encoding or "utf-8")) >= self.maxBytes:
                return True
        return False

    def doRollover(self):
        """Ruota i file di log, comprime e mantiene solo gli ultimi N."""
        if self.stream:
            self.stream.close()
            self.stream = None

        # timestamp per il nome del file
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        rotated_file = self.log_dir / f"{Path(self.baseFilename).name}.{ts}.gz"

        # comprimi il file attuale
        if os.path.exists(self.baseFilename):
            with open(self.baseFilename, "rb") as f_in, gzip.open(rotated_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(self.baseFilename)

        # mantieni solo gli ultimi N file compressi
        files = sorted(
            (f for f in self.log_dir.glob("*.gz") if f.is_file()),
            key=lambda f: f.stat().st_mtime
        )

        if len(files) > self.backupCount:
            for old_file in files[:-self.backupCount]:
                old_file.unlink()

        # riapri il file corrente vuoto
        if not self.delay:
            self.stream = self._open()


def setup_logger(console,
                 logger_name="GliAAns-UI",
                 logfile= get_app_dir() / ".log" / "log.txt",
                 level=logging.ERROR,
                 maxBytes=10*1024*1024,
                 backupCount=5):
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

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
    return logging.getLogger(logger_name)


def set_log_level(level, logger_name="GliAAns-UI"):
    logging.getLogger(logger_name).setLevel(level)


if __name__ == "__main__":
    log = setup_logger(True)

    # genera tanti log per testare rotazione + compressione
    for i in range(2000):
        log.info(f"Messaggio di log numero {i}")
