"""
Unit tests for logging configuration with sensitive data protection.
"""

import logging
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from vmledger.logging_config import (
    SensitiveDataFilter,
    JSONFormatter,
    TextFormatter,
    setup_logging,
    get_logger,
    log_with_context
)


class TestSensitiveDataFilter:
    """Test sensitive data redaction in log records."""
    
    def test_redact_password_in_context(self):
        """Test that password fields are redacted in context dict."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {
            "username": "testuser",
            "password": "secret123",
            "email": "test@example.com"
        }
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.context["username"] == "testuser"
        assert record.context["password"] == "[REDACTED]"
        assert record.context["email"] == "test@example.com"
    
    def test_redact_ssh_key_in_context(self):
        """Test that SSH key fields are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {
            "vm_id": 123,
            "ssh_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...",
            "hostname": "server01"
        }
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.context["vm_id"] == 123
        assert record.context["ssh_key"] == "[REDACTED]"
        assert record.context["hostname"] == "server01"
    
    def test_redact_nested_credentials(self):
        """Test that nested credential fields are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {
            "vm": {
                "id": 123,
                "credentials": {
                    "ssh_password": "secret",
                    "username": "root"
                }
            }
        }
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.context["vm"]["id"] == 123
        assert record.context["vm"]["credentials"]["ssh_password"] == "[REDACTED]"
        assert record.context["vm"]["credentials"]["username"] == "root"
    
    def test_redact_credentials_in_list(self):
        """Test that credentials in lists are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {
            "vms": [
                {"id": 1, "password": "secret1"},
                {"id": 2, "api_key": "key123"}
            ]
        }
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.context["vms"][0]["password"] == "[REDACTED]"
        assert record.context["vms"][1]["api_key"] == "[REDACTED]"
    
    def test_redact_ssh_private_key_in_message(self):
        """Test that SSH private keys in messages are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Key: -----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
            args=(),
            exc_info=None
        )
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert "[REDACTED SSH KEY]" in record.msg
        assert "BEGIN RSA PRIVATE KEY" not in record.msg
    
    def test_redact_jwt_token_in_message(self):
        """Test that JWT tokens in messages are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            args=(),
            exc_info=None
        )
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert "[REDACTED JWT TOKEN]" in record.msg
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in record.msg
    
    def test_redact_multiple_sensitive_keys(self):
        """Test that all sensitive key patterns are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {
            "password": "pass123",
            "ssh_key": "key123",
            "private_key": "privkey",
            "secret_key": "secret",
            "token": "token123",
            "api_key": "apikey",
            "credential": "cred",
            "auth": "auth123",
            "authorization": "Bearer token",
            "ssh_password": "sshpass",
            "safe_field": "visible"
        }
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.context["password"] == "[REDACTED]"
        assert record.context["ssh_key"] == "[REDACTED]"
        assert record.context["private_key"] == "[REDACTED]"
        assert record.context["secret_key"] == "[REDACTED]"
        assert record.context["token"] == "[REDACTED]"
        assert record.context["api_key"] == "[REDACTED]"
        assert record.context["credential"] == "[REDACTED]"
        assert record.context["auth"] == "[REDACTED]"
        assert record.context["authorization"] == "[REDACTED]"
        assert record.context["ssh_password"] == "[REDACTED]"
        assert record.context["safe_field"] == "visible"
    
    def test_no_context_attribute(self):
        """Test that filter works when record has no context."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = filter_instance.filter(record)
        
        assert result is True


class TestJSONFormatter:
    """Test JSON log formatting."""
    
    def test_format_basic_message(self):
        """Test formatting a basic log message as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")
    
    def test_format_with_context(self):
        """Test formatting with context data."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {"vm_id": 123, "action": "ping"}
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["context"]["vm_id"] == 123
        assert data["context"]["action"] == "ping"
    
    def test_format_with_request_id(self):
        """Test formatting with request ID."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "req-12345"
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["request_id"] == "req-12345"
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]
    
    def test_format_all_log_levels(self):
        """Test formatting for all log levels."""
        formatter = JSONFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL")
        ]
        
        for level_num, level_name in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level_num,
                pathname="",
                lineno=0,
                msg=f"{level_name} message",
                args=(),
                exc_info=None
            )
            
            result = formatter.format(record)
            data = json.loads(result)
            
            assert data["level"] == level_name
            assert data["message"] == f"{level_name} message"


class TestTextFormatter:
    """Test text log formatting."""
    
    def test_format_basic_message(self):
        """Test formatting a basic log message as text."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        
        assert "INFO" in result
        assert "test.logger" in result
        assert "Test message" in result
    
    def test_format_with_context(self):
        """Test formatting with context data."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.context = {"vm_id": 123}
        
        result = formatter.format(record)
        
        assert "Context:" in result
        assert "vm_id" in result
    
    def test_format_with_request_id(self):
        """Test formatting with request ID."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "req-12345"
        
        result = formatter.format(record)
        
        assert "Request ID: req-12345" in result


class TestSetupLogging:
    """Test logging setup and configuration."""
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_creates_log_directory(self, mock_settings):
        """Test that setup_logging creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "logs", "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            assert os.path.exists(os.path.dirname(log_file))
            
            # Clean up handlers to release file locks
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_configures_handlers(self, mock_settings):
        """Test that setup_logging configures console and file handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            root_logger = logging.getLogger()
            assert len(root_logger.handlers) >= 2
            
            # Check for console and file handlers
            handler_types = [type(h).__name__ for h in root_logger.handlers]
            assert "StreamHandler" in handler_types
            assert "RotatingFileHandler" in handler_types
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_applies_sensitive_data_filter(self, mock_settings):
        """Test that sensitive data filter is applied to all handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                filter_types = [type(f).__name__ for f in handler.filters]
                assert "SensitiveDataFilter" in filter_types
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_json_format(self, mock_settings):
        """Test that JSON formatter is used when configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            root_logger = logging.getLogger()
            console_handler = next(
                h for h in root_logger.handlers 
                if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
            )
            assert isinstance(console_handler.formatter, JSONFormatter)
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_text_format(self, mock_settings):
        """Test that text formatter is used when configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "text"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            root_logger = logging.getLogger()
            console_handler = next(
                h for h in root_logger.handlers 
                if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
            )
            assert isinstance(console_handler.formatter, TextFormatter)
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_configures_log_levels(self, mock_settings):
        """Test that log levels are properly configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "DEBUG"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_setup_logging_configures_rotation(self, mock_settings):
        """Test that log rotation is properly configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 50
            mock_settings.log_retention_days = 10
            
            setup_logging()
            
            root_logger = logging.getLogger()
            file_handler = next(
                h for h in root_logger.handlers 
                if isinstance(h, logging.handlers.RotatingFileHandler)
            )
            
            assert file_handler.maxBytes == 50 * 1024 * 1024  # 50 MB in bytes
            assert file_handler.backupCount == 10
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)


class TestGetLogger:
    """Test logger retrieval."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
    
    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1.name != logger2.name


class TestLogWithContext:
    """Test context logging helper."""
    
    def test_log_with_context_info(self):
        """Test logging with context at INFO level."""
        logger = logging.getLogger("test.context.info")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        
        # Create a list to capture log records
        captured_records = []
        
        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured_records.append(record)
        
        handler = CaptureHandler()
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        log_with_context(logger, "info", "Test message", vm_id=123, action="ping")
        
        assert len(captured_records) == 1
        record = captured_records[0]
        assert hasattr(record, "context")
        assert record.context["vm_id"] == 123
        assert record.context["action"] == "ping"
        
        # Clean up
        logger.removeHandler(handler)
    
    def test_log_with_context_error(self):
        """Test logging with context at ERROR level."""
        logger = logging.getLogger("test.context.error")
        logger.handlers.clear()
        logger.setLevel(logging.ERROR)
        
        # Create a list to capture log records
        captured_records = []
        
        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured_records.append(record)
        
        handler = CaptureHandler()
        handler.setLevel(logging.ERROR)
        logger.addHandler(handler)
        
        log_with_context(logger, "error", "Error occurred", error_code="E001")
        
        assert len(captured_records) == 1
        record = captured_records[0]
        assert hasattr(record, "context")
        assert record.context["error_code"] == "E001"
        
        # Clean up
        logger.removeHandler(handler)


class TestEndToEndLogging:
    """End-to-end tests for logging with sensitive data protection."""
    
    @patch("vmledger.logging_config.settings")
    def test_sensitive_data_not_logged_to_file(self, mock_settings):
        """Test that sensitive data is redacted in log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            logger = get_logger("test.e2e")
            log_with_context(
                logger,
                "info",
                "VM registered",
                vm_id=123,
                password="secret123",
                hostname="server01"
            )
            
            # Flush and close handlers to ensure data is written
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                handler.flush()
            
            # Read log file
            with open(log_file, "r") as f:
                log_content = f.read()
            
            # Find the line with our log message (skip the "Logging configured" message)
            log_lines = [line for line in log_content.strip().split('\n') if line]
            vm_log_line = None
            for line in log_lines:
                if "VM registered" in line:
                    vm_log_line = line
                    break
            
            assert vm_log_line is not None, "VM registered log not found"
            
            # Parse JSON log
            log_data = json.loads(vm_log_line)
            
            assert log_data["context"]["vm_id"] == 123
            assert log_data["context"]["password"] == "[REDACTED]"
            assert log_data["context"]["hostname"] == "server01"
            assert "secret123" not in log_content
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
    
    @patch("vmledger.logging_config.settings")
    def test_ssh_key_not_logged_to_file(self, mock_settings):
        """Test that SSH keys are redacted in log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            mock_settings.log_file_path = log_file
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            mock_settings.log_max_size_mb = 100
            mock_settings.log_retention_days = 30
            
            setup_logging()
            
            logger = get_logger("test.e2e.ssh")
            ssh_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
            logger.info(f"Processing SSH key: {ssh_key}")
            
            # Flush and close handlers to ensure data is written
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                handler.flush()
            
            # Read log file
            with open(log_file, "r") as f:
                log_content = f.read()
            
            assert "[REDACTED SSH KEY]" in log_content
            assert "BEGIN RSA PRIVATE KEY" not in log_content
            
            # Clean up handlers to release file locks
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
