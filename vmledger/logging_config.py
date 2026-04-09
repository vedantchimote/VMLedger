"""
Structured logging configuration with JSON formatting and sensitive data protection.
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

from vmledger.config import settings


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log records."""
    
    SENSITIVE_KEYS = {
        "password", "ssh_key", "private_key", "secret_key", "token",
        "api_key", "credential", "auth", "authorization", "ssh_password"
    }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log record."""
        if hasattr(record, "context") and isinstance(record.context, dict):
            record.context = self._redact_dict(record.context)
        
        # Redact message if it contains sensitive patterns
        if hasattr(record, "msg"):
            record.msg = self._redact_string(str(record.msg))
        
        return True
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive keys in dictionary."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            # Check if the key itself is sensitive (but only for leaf values, not nested dicts)
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                # If the value is a dict, we still need to recurse into it
                # Only redact if it's a leaf value (string, number, etc.)
                if isinstance(value, dict):
                    redacted[key] = self._redact_dict(value)
                elif isinstance(value, list):
                    redacted[key] = [
                        self._redact_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    # Leaf value with sensitive key name - redact it
                    redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted
    
    def _redact_string(self, text: str) -> str:
        """Redact sensitive patterns in strings."""
        # Redact anything that looks like a key or token
        import re
        
        # Redact SSH private key blocks
        text = re.sub(
            r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----",
            "[REDACTED SSH KEY]",
            text,
            flags=re.DOTALL
        )
        
        # Redact JWT tokens
        text = re.sub(
            r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[REDACTED JWT TOKEN]",
            text
        )
        
        return text


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add context if available
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        # Add request ID if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "context", "request_id"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for development."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as readable text."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        base_msg = f"[{timestamp}] {record.levelname:8s} {record.name}: {record.getMessage()}"
        
        # Add context if available
        if hasattr(record, "context"):
            context_str = json.dumps(record.context, indent=2)
            base_msg += f"\n  Context: {context_str}"
        
        # Add request ID if available
        if hasattr(record, "request_id"):
            base_msg += f"\n  Request ID: {record.request_id}"
        
        # Add exception if present
        if record.exc_info:
            base_msg += "\n" + self.formatException(record.exc_info)
        
        return base_msg


def setup_logging():
    """
    Configure application logging with structured JSON output and sensitive data protection.
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(settings.log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level))
    
    # Use JSON formatter for production, text for development
    if settings.log_format == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = TextFormatter()
    
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file_path,
        maxBytes=settings.log_max_size_mb * 1024 * 1024,  # Convert MB to bytes
        backupCount=settings.log_retention_days,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, settings.log_level))
    
    # Always use JSON for file logs
    file_formatter = JSONFormatter()
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(file_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    root_logger.info(
        "Logging configured",
        extra={
            "context": {
                "log_level": settings.log_level,
                "log_format": settings.log_format,
                "log_file": settings.log_file_path
            }
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """
    Log a message with additional context data.
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context data to include in log
    """
    log_method = getattr(logger, level.lower())
    log_method(message, extra={"context": context})
