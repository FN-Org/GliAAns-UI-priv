from datetime import datetime
import logging
import os
import gzip
import shutil
import time
from logging.handlers import BaseRotatingHandler
from pathlib import Path


class CompressedRotatingFileHandler(BaseRotatingHandler):
    def __init__(self, filename, mode="a", maxBytes=10*1024*1024,
                 backupCount=5, encoding=None, delay=False):
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.log_dir = Path(filename).parent
        super().__init__(filename, mode, encoding=encoding, delay=delay)

    def shouldRollover(self, record):
        """
        Decide se ruotare in base alla dimensione del file.
        """
        if self.stream is None:  # file non aperto
            self.stream = self._open()

        if self.maxBytes > 0:
            msg = f"{self.format(record)}\n"
            self.stream.seek(0, os.SEEK_END)
            if self.stream.tell() + len(msg.encode(self.encoding or "utf-8")) >= self.maxBytes:
                return True
        return False

    def doRollover(self):
        """
        Ruota i file di log, comprime e mantiene solo gli ultimi N.
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        # timestamp per il nome del file
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        rotated_file = f"{self.baseFilename}.{ts}.gz"

        # comprimi il file attuale
        if os.path.exists(self.baseFilename):
            with open(self.baseFilename, "rb") as f_in, gzip.open(rotated_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(self.baseFilename)

        # mantieni solo gli ultimi N file compressi
        files = [os.path.join(self.log_dir, f) for f in os.listdir(self.log_dir)
                 if f.endswith(".gz") and os.path.isfile(os.path.join(self.log_dir, f))]

        if len(files) > self.backupCount:
            files.sort(key=os.path.getmtime)
            for old_file in files[:-self.backupCount]:
                os.remove(old_file)

        # riapri il file corrente vuoto
        if not self.delay:
            self.stream = self._open()



def setup_logger(logger_name="GliAAns-UI",logfile=os.path.join("log","log.txt")):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    handler = CompressedRotatingFileHandler(
        logfile,
        maxBytes=1024*100,   # 100 KB per esempio
        backupCount=5       # mantieni solo 5 file compressi
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


if __name__ == "__main__":
    log = setup_logger()

    # genera tanti log per testare rotazione + compressione
    for i in range(2000):
        time.sleep(0.05)
        log.info(f"Messaggio di log numero {i}")
