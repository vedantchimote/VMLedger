"""
Database retry logic for handling transient errors.

This module implements retry strategies for database operations that may fail
due to transient issues like deadlocks or connection errors.

Requirements: Design - Database operation retry logic (2 attempts, 1s delay)
"""

import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any
from sqlalchemy.exc import (
    OperationalError,
    DBAPIError,
    DisconnectionError,
    TimeoutError as SQLAlchemyTimeoutError
)
from psycopg2.errors import DeadlockDetected, SerializationFailure

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar('T')


class DatabaseRetryError(Exception):
    """Raised when database operation fails after all retry attempts."""
    pass


def is_retryable_error(exc: Exception) -> bool:
    """
    Determine if a database error is retryable.
    
    Retryable errors include:
    - Deadlocks
    - Serialization failures
    - Connection errors
    - Operational errors (timeouts, connection lost)
    
    Non-retryable errors include:
    - Constraint violations
    - Data errors
    - Programming errors
    
    Args:
        exc: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    # Check for specific psycopg2 errors
    if isinstance(exc, (DeadlockDetected, SerializationFailure)):
        return True
    
    # Check for SQLAlchemy connection/operational errors
    if isinstance(exc, (OperationalError, DisconnectionError, SQLAlchemyTimeoutError)):
        return True
    
    # Check for DBAPIError with retryable causes
    if isinstance(exc, DBAPIError):
        # Check if it's a connection error
        if exc.connection_invalidated:
            return True
        
        # Check error message for retryable patterns
        error_msg = str(exc).lower()
        retryable_patterns = [
            'deadlock',
            'connection',
            'timeout',
            'lost connection',
            'server closed',
            'broken pipe',
            'serialization failure'
        ]
        
        for pattern in retryable_patterns:
            if pattern in error_msg:
                return True
    
    return False


def retry_on_db_error(
    max_retries: int = 2,
    retry_delay: float = 1.0,
    backoff_multiplier: float = 1.0
) -> Callable:
    """
    Decorator to retry database operations on transient errors.
    
    This decorator implements retry logic for database operations that may fail
    due to transient issues. It only retries on specific error types that are
    known to be transient (deadlocks, connection errors, etc.).
    
    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 1.0 = no backoff)
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_on_db_error(max_retries=2, retry_delay=1.0)
        def create_vm(db: Session, vm_data: dict):
            vm = VM(**vm_data)
            db.add(vm)
            db.commit()
            return vm
    
    Requirements: Design - Database operation retry logic (2 attempts, 1s delay)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            current_delay = retry_delay
            
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as exc:
                    last_exception = exc
                    
                    # Check if error is retryable
                    if not is_retryable_error(exc):
                        logger.debug(
                            f"Non-retryable error in {func.__name__}: {exc}"
                        )
                        raise
                    
                    # Check if we have retries left
                    if attempt >= max_retries:
                        logger.error(
                            f"Database operation {func.__name__} failed after "
                            f"{max_retries} attempts: {exc}"
                        )
                        raise DatabaseRetryError(
                            f"Operation failed after {max_retries} attempts: {exc}"
                        ) from exc
                    
                    # Log retry attempt
                    logger.warning(
                        f"Database operation {func.__name__} failed on attempt "
                        f"{attempt}/{max_retries}, retrying in {current_delay}s: {exc}"
                    )
                    
                    # Wait before retry
                    time.sleep(current_delay)
                    
                    # Apply backoff multiplier for next attempt
                    current_delay *= backoff_multiplier
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


def retry_db_operation(
    operation: Callable[..., T],
    *args: Any,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    **kwargs: Any
) -> T:
    """
    Retry a database operation with the specified retry strategy.
    
    This is a functional alternative to the decorator for cases where
    you want to apply retry logic to a specific operation without decorating
    the entire function.
    
    Args:
        operation: Function to execute with retry logic
        *args: Positional arguments to pass to operation
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Delay between retries in seconds (default: 1.0)
        **kwargs: Keyword arguments to pass to operation
        
    Returns:
        Result of the operation
        
    Raises:
        DatabaseRetryError: If operation fails after all retries
        
    Example:
        result = retry_db_operation(
            db.query(VM).filter(VM.id == vm_id).first,
            max_retries=2,
            retry_delay=1.0
        )
    
    Requirements: Design - Database operation retry logic (2 attempts, 1s delay)
    """
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            return operation(*args, **kwargs)
            
        except Exception as exc:
            last_exception = exc
            
            # Check if error is retryable
            if not is_retryable_error(exc):
                logger.debug(
                    f"Non-retryable error in database operation: {exc}"
                )
                raise
            
            # Check if we have retries left
            if attempt >= max_retries:
                logger.error(
                    f"Database operation failed after {max_retries} attempts: {exc}"
                )
                raise DatabaseRetryError(
                    f"Operation failed after {max_retries} attempts: {exc}"
                ) from exc
            
            # Log retry attempt
            logger.warning(
                f"Database operation failed on attempt {attempt}/{max_retries}, "
                f"retrying in {retry_delay}s: {exc}"
            )
            
            # Wait before retry
            time.sleep(retry_delay)
    
    # This should never be reached, but just in case
    if last_exception:
        raise last_exception
