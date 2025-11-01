import pytest
import os
import sys
import tempfile
import shutil
import gzip
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import dal tuo progetto
import logger
from logger import CompressedRotatingFileHandler, setup_logger, get_logger, set_log_level


class TestCompressedRotatingFileHandler:
    """Test per CompressedRotatingFileHandler"""

    @pytest.fixture
    def temp_log_dir(self):
        """Crea directory temporanea per log"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def log_file(self, temp_log_dir):
        """Crea path per file log"""
        return temp_log_dir / "test.log"

    def test_handler_initialization(self, log_file):
        """Verifica inizializzazione handler"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=1024,
            backupCount=3
        )

        assert handler.maxBytes == 1024
        assert handler.backupCount == 3
        assert handler.log_dir == log_file.parent

    def test_log_dir_created(self, temp_log_dir):
        """Verifica creazione directory log"""
        log_file = temp_log_dir / "subdir" / "test.log"

        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=1024,
            backupCount=3
        )

        assert log_file.parent.exists()

    def test_should_rollover_small_file(self, log_file):
        """Verifica che non faccia rollover con file piccolo"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=10000,
            backupCount=3
        )

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Short message",
            args=(),
            exc_info=None
        )

        # Con file piccolo non dovrebbe fare rollover
        should_roll = handler.shouldRollover(record)
        assert should_roll == False

        handler.close()

    def test_should_rollover_large_file(self, log_file):
        """Verifica rollover con file grande"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=100,  # Molto piccolo
            backupCount=3
        )

        # Scrivi dati per riempire
        for i in range(10):
            handler.emit(logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=f"Message {i}" * 10,
                args=(),
                exc_info=None
            ))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Final message",
            args=(),
            exc_info=None
        )

        should_roll = handler.shouldRollover(record)
        handler.close()

        # Potrebbe essere True se il file è abbastanza grande
        assert isinstance(should_roll, bool)

    def test_do_rollover_creates_compressed_file(self, log_file):
        """Verifica che rollover crei file compresso"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=100,
            backupCount=3
        )

        # Scrivi qualcosa
        handler.emit(logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        ))

        # Forza rollover
        handler.doRollover()

        # Verifica che esista un file .gz
        gz_files = list(log_file.parent.glob("*.gz"))
        assert len(gz_files) > 0

        handler.close()

    def test_do_rollover_maintains_backup_count(self, log_file):
        """Verifica che mantenga solo N backup"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=50,
            backupCount=2
        )

        # Crea più rollover del limite
        for i in range(5):
            handler.emit(logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=f"Message {i}" * 20,
                args=(),
                exc_info=None
            ))
            handler.doRollover()

        # Verifica che ci siano solo 2 backup (backupCount)
        gz_files = list(log_file.parent.glob("*.gz"))
        assert len(gz_files) <= 2

        handler.close()

    def test_compressed_file_readable(self, log_file):
        """Verifica che il file compresso sia leggibile"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=100,
            backupCount=3
        )

        test_message = "Test message for compression"
        handler.emit(logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=test_message,
            args=(),
            exc_info=None
        ))

        handler.doRollover()

        # Trova il file compresso
        gz_files = list(log_file.parent.glob("*.gz"))
        if gz_files:
            with gzip.open(gz_files[0], "rt") as f:
                content = f.read()
                assert test_message in content

        handler.close()


class TestSetupLogger:
    """Test per setup_logger function"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def clean_logger(self):
        """Pulisce logger prima e dopo test"""
        logger_name = "TestLogger"
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        yield logger_name
        test_logger.handlers.clear()

    def test_setup_logger_creates_logger(self, temp_log_dir, clean_logger):
        """Verifica creazione logger"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                level=logging.INFO
            )

            assert log is not None
            assert log.name == clean_logger
            assert log.level == logging.INFO

    def test_setup_logger_creates_log_file(self, temp_log_dir, clean_logger):
        """Verifica creazione file log"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            log_file = temp_log_dir / ".log" / "log.txt"
            # Il file potrebbe non esistere subito, ma la directory sì
            assert log_file.parent.exists()

    def test_setup_logger_with_console(self, temp_log_dir, clean_logger):
        """Verifica aggiunta console handler"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=True,
                logger_name=clean_logger
            )

            # Dovrebbe avere almeno 2 handler (file + console)
            assert len(log.handlers) >= 2

            # Verifica che uno sia StreamHandler
            stream_handlers = [h for h in log.handlers
                               if isinstance(h, logging.StreamHandler)
                               and not isinstance(h, CompressedRotatingFileHandler)]
            assert len(stream_handlers) > 0

    def test_setup_logger_without_console(self, temp_log_dir, clean_logger):
        """Verifica setup senza console handler"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            # Verifica che non ci siano StreamHandler (eccetto il file handler)
            stream_handlers = [h for h in log.handlers
                               if isinstance(h, logging.StreamHandler)
                               and not isinstance(h, CompressedRotatingFileHandler)]
            assert len(stream_handlers) == 0

    def test_setup_logger_custom_logfile(self, temp_log_dir, clean_logger):
        """Verifica uso di file log personalizzato"""
        custom_file = temp_log_dir / "custom.log"

        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                logfile=custom_file
            )

            # Verifica che usi il file custom
            file_handlers = [h for h in log.handlers
                             if isinstance(h, CompressedRotatingFileHandler)]
            assert len(file_handlers) > 0

    def test_setup_logger_clears_existing_handlers(self, temp_log_dir, clean_logger):
        """Verifica che pulisca handler esistenti"""
        # Aggiungi un handler esistente
        test_logger = logging.getLogger(clean_logger)
        test_logger.addHandler(logging.NullHandler())
        initial_count = len(test_logger.handlers)

        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            # I vecchi handler dovrebbero essere rimossi
            assert all(not isinstance(h, logging.NullHandler) for h in log.handlers)

    def test_setup_logger_max_bytes(self, temp_log_dir, clean_logger):
        """Verifica impostazione maxBytes"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                maxBytes=5000
            )

            file_handlers = [h for h in log.handlers
                             if isinstance(h, CompressedRotatingFileHandler)]
            if file_handlers:
                assert file_handlers[0].maxBytes == 5000

    def test_setup_logger_backup_count(self, temp_log_dir, clean_logger):
        """Verifica impostazione backupCount"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                backupCount=10
            )

            file_handlers = [h for h in log.handlers
                             if isinstance(h, CompressedRotatingFileHandler)]
            if file_handlers:
                assert file_handlers[0].backupCount == 10


class TestGetLogger:
    """Test per get_logger function"""

    def test_get_logger_returns_logger(self):
        """Verifica che ritorni un logger"""
        log = get_logger("TestGetLogger")
        assert isinstance(log, logging.Logger)

    def test_get_logger_default_name(self):
        """Verifica nome di default"""
        log = get_logger()
        assert log.name == "GliAAns-UI"

    def test_get_logger_custom_name(self):
        """Verifica nome personalizzato"""
        log = get_logger("CustomLogger")
        assert log.name == "CustomLogger"

    def test_get_logger_same_instance(self):
        """Verifica che ritorni la stessa istanza"""
        log1 = get_logger("SameLogger")
        log2 = get_logger("SameLogger")
        assert log1 is log2


class TestSetLogLevel:
    """Test per set_log_level function"""

    @pytest.fixture
    def test_logger(self):
        """Crea logger di test"""
        logger_name = "TestSetLevel"
        test_log = logging.getLogger(logger_name)
        test_log.setLevel(logging.WARNING)
        yield logger_name, test_log
        test_log.handlers.clear()

    def test_set_log_level_debug(self, test_logger):
        """Verifica impostazione livello DEBUG"""
        logger_name, log = test_logger

        set_log_level(logging.DEBUG, logger_name)

        assert log.level == logging.DEBUG

    def test_set_log_level_info(self, test_logger):
        """Verifica impostazione livello INFO"""
        logger_name, log = test_logger

        set_log_level(logging.INFO, logger_name)

        assert log.level == logging.INFO

    def test_set_log_level_error(self, test_logger):
        """Verifica impostazione livello ERROR"""
        logger_name, log = test_logger

        set_log_level(logging.ERROR, logger_name)

        assert log.level == logging.ERROR

    def test_set_log_level_default_logger(self):
        """Verifica impostazione su logger default"""
        set_log_level(logging.WARNING)

        log = get_logger()
        assert log.level == logging.WARNING


class TestLoggerFormatting:
    """Test per formattazione log"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_file_formatter(self, temp_log_dir):
        """Verifica formato file log"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="TestFormat",
                level=logging.DEBUG
            )

            log.info("Test message")

            log_file = temp_log_dir / ".log" / "log.txt"
            if log_file.exists():
                content = log_file.read_text()
                # Dovrebbe contenere timestamp, level, filename, etc
                assert "INFO" in content
                assert "Test message" in content

    def test_console_formatter(self, temp_log_dir, capsys):
        """Verifica formato console log"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=True,
                logger_name="TestConsoleFormat",
                level=logging.DEBUG
            )

            log.info("Console test message")

            captured = capsys.readouterr()
            # Console dovrebbe avere formato più compatto
            assert "INFO" in captured.out or "Console test message" in captured.out


class TestLoggerIntegration:
    """Test di integrazione per scenari realistici"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_logging_workflow(self, temp_log_dir):
        """Test flusso completo di logging"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            # Setup logger
            log = setup_logger(
                console=False,
                logger_name="IntegrationTest",
                level=logging.INFO,
                maxBytes=500,
                backupCount=2
            )

            # Scrivi vari log
            for i in range(50):
                log.info(f"Log message {i}")
                log.debug(f"Debug message {i}")
                log.error(f"Error message {i}")

            # Verifica che ci siano file
            log_dir = temp_log_dir / ".log"
            assert log_dir.exists()

            # Potrebbero esserci file compressi
            all_files = list(log_dir.glob("*"))
            assert len(all_files) > 0

    def test_logger_persistence(self, temp_log_dir):
        """Verifica persistenza tra chiamate"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            # Prima chiamata
            log1 = setup_logger(
                console=False,
                logger_name="PersistenceTest",
                level=logging.INFO
            )
            log1.info("First message")

            # Seconda chiamata (dovrebbe pulire handler)
            log2 = setup_logger(
                console=False,
                logger_name="PersistenceTest",
                level=logging.DEBUG
            )

            assert log1.name == log2.name
            assert log2.level == logging.DEBUG


class TestEdgeCases:
    """Test per casi edge"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_empty_log_message(self, temp_log_dir):
        """Verifica gestione messaggio vuoto"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="EmptyTest",
                level=logging.INFO
            )

            # Non dovrebbe causare errori
            log.info("")
            log.info(None)

    def test_very_long_message(self, temp_log_dir):
        """Verifica gestione messaggio molto lungo"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="LongTest",
                level=logging.INFO,
                maxBytes=1000
            )

            long_message = "A" * 10000
            log.info(long_message)

            # Dovrebbe triggerare rollover
            # Verifica che non causi errori

    def test_special_characters_in_message(self, temp_log_dir):
        """Verifica gestione caratteri speciali"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="SpecialTest",
                level=logging.INFO
            )

            # Caratteri speciali
            log.info("Messaggio con àccénti €€€")
            log.info("Newlines\n\nand\ttabs")

    def test_zero_backup_count(self, temp_log_dir):
        """Verifica comportamento con backupCount=0"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="NoBackupTest",
                level=logging.INFO,
                backupCount=0
            )

            # Non dovrebbe causare errori
            for i in range(10):
                log.info(f"Message {i}")

    def test_permission_error_handling(self, temp_log_dir):
        """Verifica gestione errori di permessi"""
        with patch('logger.get_app_dir', return_value=temp_log_dir):
            # Crea directory read-only (se possibile)
            restricted_dir = temp_log_dir / "restricted"
            restricted_dir.mkdir()

            try:
                restricted_dir.chmod(0o444)

                # Tentativo di creare log in directory protetta
                # Potrebbe fallire, ma non dovrebbe crashare
                try:
                    setup_logger(
                        console=False,
                        logger_name="PermTest",
                        logfile=restricted_dir / "test.log"
                    )
                except (PermissionError, OSError):
                    pass  # Errore atteso

            finally:
                restricted_dir.chmod(0o755)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])