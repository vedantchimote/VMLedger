"""
Unit tests for database retry logic.

Tests the retry decorator and functional retry wrapper for database operations
with transient errors like deadlocks and connection failures.

Requirements: Design - Database operation retry logic (2 attempts, 1s delay)
"""

import pytest
import time
from unittest.mock import Mock, patch
from sqlalchemy.exc import (
    OperationalError,
    DBAPIError,
    DisconnectionError,
    IntegrityError
)
from psycopg2.errors import DeadlockDetected, SerializationFailure

from vmledger.database_retry import (
    retry_on_db_error,
    retry_db_operation,
    is_retryable_error,
    DatabaseRetryError
)


class TestIsRetryableError:
    """Test error classification for retry logic."""
    
    def test_deadlock_detected_is_retryable(self):
        """DeadlockDetected errors should be retryable."""
        exc = DeadlockDetected("deadlock detected")
        assert is_retryable_error(exc) is True
    
    def test_serialization_failure_is_retryable(self):
        """SerializationFailure errors should be retryable."""
        exc = SerializationFailure("could not serialize access")
        assert is_retryable_error(exc) is True
    
    def test_operational_error_is_retryable(self):
        """OperationalError should be retryable."""
        exc = OperationalError("connection timeout", None, None)
        assert is_retryable_error(exc) is True
    
    def test_disconnection_error_is_retryable(self):
        """DisconnectionError should be retryable."""
        exc = DisconnectionError("connection lost")
        assert is_retryable_error(exc) is True
    
    def test_integrity_error_is_not_retryable(self):
        """IntegrityError (constraint violation) should not be retryable."""
        exc = IntegrityError("unique constraint violated", None, None)
        assert is_retryable_error(exc) is False
    
    def test_value_error_is_not_retryable(self):
        """ValueError should not be retryable."""
        exc = ValueError("invalid value")
        assert is_retryable_error(exc) is False
    
    def test_dbapi_error_with_connection_invalidated(self):
        """DBAPIError with connection_invalidated should be retryable."""
        exc = DBAPIError("connection error", None, None)
        exc.connection_invalidated = True
        assert is_retryable_error(exc) is True
    
    def test_dbapi_error_with_deadlock_message(self):
        """DBAPIError with 'deadlock' in message should be retryable."""
        exc = DBAPIError("deadlock detected in transaction", None, None)
        assert is_retryable_error(exc) is True
    
    def test_dbapi_error_with_connection_message(self):
        """DBAPIError with 'connection' in message should be retryable."""
        exc = DBAPIError("lost connection to server", None, None)
        assert is_retryable_error(exc) is True


class TestRetryOnDbErrorDecorator:
    """Test the retry_on_db_error decorator."""
    
    def test_successful_operation_no_retry(self):
        """Successful operation should not trigger retries."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_operation()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retryable_error_succeeds_on_second_attempt(self):
        """Retryable error should retry and succeed on second attempt."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def operation_fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeadlockDetected("deadlock detected")
            return "success"
        
        start_time = time.time()
        result = operation_fails_once()
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert call_count == 2
        # Should have waited at least 0.1 seconds for retry
        assert elapsed >= 0.1
    
    def test_retryable_error_fails_after_max_retries(self):
        """Retryable error should fail after max retries."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def operation_always_fails():
            nonlocal call_count
            call_count += 1
            raise DeadlockDetected("deadlock detected")
        
        with pytest.raises(DatabaseRetryError) as exc_info:
            operation_always_fails()
        
        assert call_count == 2
        assert "failed after 2 attempts" in str(exc_info.value)
    
    def test_non_retryable_error_fails_immediately(self):
        """Non-retryable error should fail immediately without retry."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def operation_with_integrity_error():
            nonlocal call_count
            call_count += 1
            raise IntegrityError("unique constraint violated", None, None)
        
        with pytest.raises(IntegrityError):
            operation_with_integrity_error()
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    def test_retry_delay_is_applied(self):
        """Retry delay should be applied between attempts."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.2)
        def operation_fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("connection timeout", None, None)
            return "success"
        
        start_time = time.time()
        result = operation_fails_once()
        elapsed = time.time() - start_time
        
        assert result == "success"
        # Should have waited at least 0.2 seconds
        assert elapsed >= 0.2
    
    def test_exponential_backoff(self):
        """Exponential backoff should increase delay between retries."""
        call_count = 0
        
        @retry_on_db_error(max_retries=3, retry_delay=0.1, backoff_multiplier=2.0)
        def operation_fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OperationalError("connection timeout", None, None)
            return "success"
        
        start_time = time.time()
        result = operation_fails_twice()
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert call_count == 3
        # First retry: 0.1s, second retry: 0.2s = 0.3s total minimum
        assert elapsed >= 0.3
    
    def test_decorator_preserves_function_metadata(self):
        """Decorator should preserve function name and docstring."""
        @retry_on_db_error()
        def my_function():
            """My docstring."""
            pass
        
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."
    
    def test_decorator_with_arguments(self):
        """Decorator should work with functions that have arguments."""
        call_count = 0
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def operation_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeadlockDetected("deadlock")
            return f"{a}-{b}-{c}"
        
        result = operation_with_args("x", "y", c="z")
        
        assert result == "x-y-z"
        assert call_count == 2


class TestRetryDbOperation:
    """Test the retry_db_operation functional wrapper."""
    
    def test_successful_operation_no_retry(self):
        """Successful operation should not trigger retries."""
        call_count = 0
        
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = retry_db_operation(
            successful_operation,
            max_retries=2,
            retry_delay=0.1
        )
        
        assert result == "success"
        assert call_count == 1
    
    def test_retryable_error_succeeds_on_second_attempt(self):
        """Retryable error should retry and succeed on second attempt."""
        call_count = 0
        
        def operation_fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeadlockDetected("deadlock detected")
            return "success"
        
        result = retry_db_operation(
            operation_fails_once,
            max_retries=2,
            retry_delay=0.1
        )
        
        assert result == "success"
        assert call_count == 2
    
    def test_retryable_error_fails_after_max_retries(self):
        """Retryable error should fail after max retries."""
        call_count = 0
        
        def operation_always_fails():
            nonlocal call_count
            call_count += 1
            raise DeadlockDetected("deadlock detected")
        
        with pytest.raises(DatabaseRetryError) as exc_info:
            retry_db_operation(
                operation_always_fails,
                max_retries=2,
                retry_delay=0.1
            )
        
        assert call_count == 2
        assert "failed after 2 attempts" in str(exc_info.value)
    
    def test_non_retryable_error_fails_immediately(self):
        """Non-retryable error should fail immediately without retry."""
        call_count = 0
        
        def operation_with_integrity_error():
            nonlocal call_count
            call_count += 1
            raise IntegrityError("unique constraint violated", None, None)
        
        with pytest.raises(IntegrityError):
            retry_db_operation(
                operation_with_integrity_error,
                max_retries=2,
                retry_delay=0.1
            )
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    def test_operation_with_arguments(self):
        """Functional wrapper should work with arguments."""
        call_count = 0
        
        def operation_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DeadlockDetected("deadlock")
            return f"{a}-{b}-{c}"
        
        result = retry_db_operation(
            operation_with_args,
            "x", "y",
            c="z",
            max_retries=2,
            retry_delay=0.1
        )
        
        assert result == "x-y-z"
        assert call_count == 2
    
    def test_retry_delay_is_applied(self):
        """Retry delay should be applied between attempts."""
        call_count = 0
        
        def operation_fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("connection timeout", None, None)
            return "success"
        
        start_time = time.time()
        result = retry_db_operation(
            operation_fails_once,
            max_retries=2,
            retry_delay=0.2
        )
        elapsed = time.time() - start_time
        
        assert result == "success"
        # Should have waited at least 0.2 seconds
        assert elapsed >= 0.2


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_database_deadlock_scenario(self):
        """Simulate a database deadlock that resolves on retry."""
        attempts = []
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def update_vm_with_deadlock():
            attempts.append(time.time())
            if len(attempts) == 1:
                # First attempt: deadlock
                raise DeadlockDetected("deadlock detected")
            # Second attempt: success
            return {"id": 1, "hostname": "updated"}
        
        result = update_vm_with_deadlock()
        
        assert result == {"id": 1, "hostname": "updated"}
        assert len(attempts) == 2
        # Verify delay between attempts
        assert attempts[1] - attempts[0] >= 0.1
    
    def test_connection_lost_scenario(self):
        """Simulate a lost database connection that recovers."""
        attempts = []
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def query_with_connection_loss():
            attempts.append(time.time())
            if len(attempts) == 1:
                # First attempt: connection lost
                raise DisconnectionError("connection lost")
            # Second attempt: success
            return [{"id": 1}, {"id": 2}]
        
        result = query_with_connection_loss()
        
        assert len(result) == 2
        assert len(attempts) == 2
    
    def test_permanent_constraint_violation(self):
        """Constraint violations should not be retried."""
        attempts = []
        
        @retry_on_db_error(max_retries=2, retry_delay=0.1)
        def insert_duplicate():
            attempts.append(time.time())
            raise IntegrityError("duplicate key value", None, None)
        
        with pytest.raises(IntegrityError):
            insert_duplicate()
        
        # Should only attempt once
        assert len(attempts) == 1
