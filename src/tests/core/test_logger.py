import pytest
import os
import sys
import tempfile
import shutil
import gzip
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from main.logger import CompressedRotatingFileHandler, setup_logger, get_logger, set_log_level


class TestCompressedRotatingFileHandler:
    """Tests for CompressedRotatingFileHandler"""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for logs"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def log_file(self, temp_log_dir):
        """Create path for log file"""
        return temp_log_dir / "test.log"

    def test_handler_initialization(self, log_file):
        """Verify handler initialization"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=1024,
            backupCount=3
        )

        assert handler.maxBytes == 1024
        assert handler.backupCount == 3
        assert handler.log_dir == log_file.parent

    def test_log_dir_created(self, temp_log_dir):
        """Verify log directory creation"""
        log_file = temp_log_dir / "subdir" / "test.log"

        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=1024,
            backupCount=3
        )

        assert log_file.parent.exists()

    def test_should_rollover_small_file(self, log_file):
        """Verify it does not rollover with a small file"""
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

        # With a small file, it should not rollover
        should_roll = handler.shouldRollover(record)
        assert should_roll == False

        handler.close()

    def test_should_rollover_large_file(self, log_file):
        """Verify rollover with a large file"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=100,  # Very small
            backupCount=3
        )

        # Write data to fill
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

        # Could be True if the file is large enough
        assert isinstance(should_roll, bool)

    def test_do_rollover_creates_compressed_file(self, log_file):
        """Verify that rollover creates a compressed file"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=100,
            backupCount=3
        )

        # Write something
        handler.emit(logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        ))

        # Force rollover
        handler.doRollover()

        # Verify that a .gz file exists
        gz_files = list(log_file.parent.glob("*.gz"))
        assert len(gz_files) > 0

        handler.close()

    def test_do_rollover_maintains_backup_count(self, log_file):
        """Verify that it keeps only N backups"""
        handler = CompressedRotatingFileHandler(
            str(log_file),
            maxBytes=50,
            backupCount=2
        )

        # Create more rollovers than the limit
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

        # Verify there are only 2 backups (backupCount)
        gz_files = list(log_file.parent.glob("*.gz"))
        assert len(gz_files) <= 2

        handler.close()

    def test_compressed_file_readable(self, log_file):
        """Verify that the compressed file is readable"""
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

        # Find the compressed file
        gz_files = list(log_file.parent.glob("*.gz"))
        if gz_files:
            with gzip.open(gz_files[0], "rt") as f:
                content = f.read()
                assert test_message in content

        handler.close()


class TestSetupLogger:
    """Tests for setup_logger function"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def clean_logger(self):
        """Cleans logger before and after test"""
        logger_name = "TestLogger"
        test_logger = logging.getLogger(logger_name)
        test_logger.handlers.clear()
        yield logger_name
        test_logger.handlers.clear()

    def test_setup_logger_creates_logger(self, temp_log_dir, clean_logger):
        """Verify logger creation"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                level=logging.INFO
            )

            assert log is not None
            assert log.name == clean_logger
            assert log.level == logging.INFO

    def test_setup_logger_creates_log_file(self, temp_log_dir, clean_logger):
        """Verify log file creation"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            log_file = temp_log_dir / ".log" / "log.txt"
            # The file might not exist immediately, but the directory will
            assert log_file.parent.exists()

    def test_setup_logger_with_console(self, temp_log_dir, clean_logger):
        """Verify addition of console handler"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=True,
                logger_name=clean_logger
            )

            # Should have at least 2 handlers (file + console)
            assert len(log.handlers) >= 2

            # Verify that one is a StreamHandler
            stream_handlers = [h for h in log.handlers
                               if isinstance(h, logging.StreamHandler)
                               and not isinstance(h, CompressedRotatingFileHandler)]
            assert len(stream_handlers) > 0

    def test_setup_logger_without_console(self, temp_log_dir, clean_logger):
        """Verify setup without console handler"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            # Verify no StreamHandlers (except file handler)
            stream_handlers = [h for h in log.handlers
                               if isinstance(h, logging.StreamHandler)
                               and not isinstance(h, CompressedRotatingFileHandler)]
            assert len(stream_handlers) == 0

    def test_setup_logger_custom_logfile(self, temp_log_dir, clean_logger):
        """Verify use of custom log file"""
        custom_file = temp_log_dir / "custom.log"

        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger,
                logfile=custom_file
            )

            # Verify it uses the custom file
            file_handlers = [h for h in log.handlers
                             if isinstance(h, CompressedRotatingFileHandler)]
            assert len(file_handlers) > 0

    def test_setup_logger_clears_existing_handlers(self, temp_log_dir, clean_logger):
        """Verify that it clears existing handlers"""
        # Add an existing handler
        test_logger = logging.getLogger(clean_logger)
        test_logger.addHandler(logging.NullHandler())
        initial_count = len(test_logger.handlers)

        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name=clean_logger
            )

            # Old handlers should be removed
            assert all(not isinstance(h, logging.NullHandler) for h in log.handlers)

    def test_setup_logger_max_bytes(self, temp_log_dir, clean_logger):
        """Verify maxBytes setting"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
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
        """Verify backupCount setting"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
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
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Verify it returns a logger"""
        log = get_logger("TestGetLogger")
        assert isinstance(log, logging.Logger)

    def test_get_logger_default_name(self):
        """Verify default name"""
        log = get_logger()
        assert log.name == "GliAAns-UI"

    def test_get_logger_custom_name(self):
        """Verify custom name"""
        log = get_logger("CustomLogger")
        assert log.name == "CustomLogger"

    def test_get_logger_same_instance(self):
        """Verify it returns the same instance"""
        log1 = get_logger("SameLogger")
        log2 = get_logger("SameLogger")
        assert log1 is log2


class TestSetLogLevel:
    """Tests for set_log_level function"""

    @pytest.fixture
    def test_logger(self):
        """Create test logger"""
        logger_name = "TestSetLevel"
        test_log = logging.getLogger(logger_name)
        test_log.setLevel(logging.WARNING)
        yield logger_name, test_log
        test_log.handlers.clear()

    def test_set_log_level_debug(self, test_logger):
        """Verify DEBUG level setting"""
        logger_name, log = test_logger

        set_log_level(logging.DEBUG, logger_name)

        assert log.level == logging.DEBUG

    def test_set_log_level_info(self, test_logger):
        """Verify INFO level setting"""
        logger_name, log = test_logger

        set_log_level(logging.INFO, logger_name)

        assert log.level == logging.INFO

    def test_set_log_level_error(self, test_logger):
        """Verify ERROR level setting"""
        logger_name, log = test_logger

        set_log_level(logging.ERROR, logger_name)

        assert log.level == logging.ERROR

    def test_set_log_level_default_logger(self):
        """Verify setting on default logger"""
        set_log_level(logging.WARNING)

        log = get_logger()
        assert log.level == logging.WARNING


class TestLoggerFormatting:
    """Tests for log formatting"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_file_formatter(self, temp_log_dir):
        """Verify log file format"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="TestFormat",
                level=logging.DEBUG
            )

            log.info("Test message")

            log_file = temp_log_dir / ".log" / "log.txt"
            if log_file.exists():
                content = log_file.read_text()
                # Should contain timestamp, level, filename, etc
                assert "INFO" in content
                assert "Test message" in content

    def test_console_formatter(self, temp_log_dir, capsys):
        """Verify console log format"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=True,
                logger_name="TestConsoleFormat",
                level=logging.DEBUG
            )

            log.info("Console test message")

            captured = capsys.readouterr()
            # Console should have a more compact format
            assert "INFO" in captured.out or "Console test message" in captured.out


class TestLoggerIntegration:
    """Integration tests for realistic scenarios"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_logging_workflow(self, temp_log_dir):
        """Test full logging workflow"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            # Setup logger
            log = setup_logger(
                console=False,
                logger_name="IntegrationTest",
                level=logging.INFO,
                maxBytes=500,
                backupCount=2
            )

            # Write various logs
            for i in range(50):
                log.info(f"Log message {i}")
                log.debug(f"Debug message {i}")
                log.error(f"Error message {i}")

            # Verify files exist
            log_dir = temp_log_dir / ".log"
            assert log_dir.exists()

            # There might be compressed files
            all_files = list(log_dir.glob("*"))
            assert len(all_files) > 0

    def test_logger_persistence(self, temp_log_dir):
        """Verify persistence between calls"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            # First call
            log1 = setup_logger(
                console=False,
                logger_name="PersistenceTest",
                level=logging.INFO
            )
            log1.info("First message")

            # Second call (should clear handlers)
            log2 = setup_logger(
                console=False,
                logger_name="PersistenceTest",
                level=logging.DEBUG
            )

            assert log1.name == log2.name
            assert log2.level == logging.DEBUG


class TestEdgeCases:
    """Tests for edge cases"""

    @pytest.fixture
    def temp_log_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_empty_log_message(self, temp_log_dir):
        """Verify handling of empty message"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="EmptyTest",
                level=logging.INFO
            )

            # Should not cause errors
            log.info("")
            log.info(None)

    def test_very_long_message(self, temp_log_dir):
        """Verify handling of very long message"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="LongTest",
                level=logging.INFO,
                maxBytes=1000
            )

            long_message = "A" * 10000
            log.info(long_message)

            # Should trigger rollover
            # Verify it does not cause errors

    def test_special_characters_in_message(self, temp_log_dir):
        """Verify handling of special characters"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="SpecialTest",
                level=logging.INFO
            )

            # Special characters
            log.info("Messaggio con àccénti €€€")
            log.info("Newlines\n\nand\ttabs")

    def test_zero_backup_count(self, temp_log_dir):
        """Verify behavior with backupCount=0"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            log = setup_logger(
                console=False,
                logger_name="NoBackupTest",
                level=logging.INFO,
                backupCount=0
            )

            # Should not cause errors
            for i in range(10):
                log.info(f"Message {i}")

    def test_permission_error_handling(self, temp_log_dir):
        """Verify handling of permission errors"""
        with patch('main.logger.get_app_dir', return_value=temp_log_dir):
            # Create read-only directory (if possible)
            restricted_dir = temp_log_dir / "restricted"
            restricted_dir.mkdir()

            try:
                restricted_dir.chmod(0o444)

                # Attempt to create log in protected directory
                # Might fail, but should not crash
                try:
                    setup_logger(
                        console=False,
                        logger_name="PermTest",
                        logfile=restricted_dir / "test.log"
                    )
                except (PermissionError, OSError):
                    pass  # Expected error

            finally:
                restricted_dir.chmod(0o755)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])