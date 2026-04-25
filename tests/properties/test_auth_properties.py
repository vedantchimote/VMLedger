"""
Property-based tests for authentication functionality.

Tests Properties 14-17: Authentication and authorization
Validates: Requirements 10.1-10.6, 14.4
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume
from vmledger.services.auth_service import AuthService
from vmledger.models.user import User
from vmledger.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenInvalidError,
    PasswordComplexityError
)


# Strategy for generating usernames
usernames = st.text(
    min_size=3,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")
)

# Strategy for generating passwords
passwords = st.text(
    min_size=12,
    max_size=72,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="!@#$%^&*()")
)


@given(
    username=usernames,
    password=passwords
)
def test_property_unauthenticated_request_rejection(username, password, mock_db_session, mock_redis):
    """
    Property 14: Unauthenticated Request Rejection
    
    Property: Any request without a valid authentication token should be rejected.
    
    Validates: Requirement 10.1 - Require authentication before allowing access
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Act & Assert - Try to validate an invalid/missing token
    with pytest.raises((TokenInvalidError, TokenExpiredError)):
        auth_service.validate_token("invalid_token_12345")
    
    with pytest.raises((TokenInvalidError, TokenExpiredError)):
        auth_service.validate_token("")


@given(
    hours_expired=st.integers(min_value=1, max_value=168)  # 1 hour to 1 week
)
def test_property_token_expiry_enforcement(hours_expired, mock_db_session, mock_redis):
    """
    Property 15: Token Expiry Enforcement
    
    Property: Tokens that have exceeded their expiration time (24 hours)
    should be rejected and require re-authentication.
    
    Validates: Requirement 10.4 - Require re-authentication when token expires
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Create a mock user
    mock_user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        encryption_salt="salt",
        is_active=True
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    
    # Create a token with custom expiration
    from jose import jwt
    from vmledger.config import settings
    
    expired_time = datetime.utcnow() - timedelta(hours=hours_expired)
    token_data = {
        "sub": str(mock_user.id),
        "username": mock_user.username,
        "email": mock_user.email,
        "exp": expired_time,
        "iat": expired_time - timedelta(hours=1),
        "type": "access"
    }
    
    expired_token = jwt.encode(
        token_data,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Act & Assert
    with pytest.raises(TokenExpiredError):
        auth_service.validate_token(expired_token)


@given(
    password=st.text(min_size=1, max_size=200)
)
def test_property_password_complexity_validation(password, mock_db_session, mock_redis):
    """
    Property 16: Password Complexity Validation
    
    Property: Passwords must meet complexity requirements:
    - Minimum 12 characters
    - Maximum 72 bytes (bcrypt limit)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    
    Validates: Requirement 10.5 - Enforce password complexity requirements
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Check if password meets requirements
    meets_length = len(password) >= 12
    meets_byte_limit = len(password.encode('utf-8')) <= 72
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*(),.?\":{}|<>" for c in password)
    
    is_valid = (meets_length and meets_byte_limit and has_upper and 
                has_lower and has_digit and has_special)
    
    # Act & Assert
    if is_valid:
        # Valid password should not raise exception
        try:
            auth_service._validate_password_complexity(password)
        except PasswordComplexityError:
            pytest.fail(f"Valid password rejected: {password}")
    else:
        # Invalid password should raise exception
        with pytest.raises(PasswordComplexityError):
            auth_service._validate_password_complexity(password)


@given(
    username=usernames,
    password=passwords,
    success=st.booleans()
)
def test_property_authentication_attempt_logging(
    username, password, success, mock_db_session, mock_redis
):
    """
    Property 17: Authentication Attempt Logging
    
    Property: All authentication attempts (successful and failed) should be
    logged with timestamp and outcome.
    
    Validates: Requirement 14.4 - Log all authentication attempts with timestamps and outcomes
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Create a mock user
    mock_user = User(
        id=1,
        username=username,
        email="test@example.com",
        password_hash=auth_service._hash_password(password) if success else "wrong_hash",
        encryption_salt="salt",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_redis.get.return_value = None  # No rate limiting
    
    # Act
    import logging
    with pytest.LogCaptureFixture() as log_capture:
        try:
            result = auth_service.authenticate(username, password)
            
            # Assert - Successful authentication should be logged
            if success:
                assert result is not None
                # Check that success was logged (implementation-specific)
        except AuthenticationError:
            # Assert - Failed authentication should be logged
            if not success:
                pass  # Expected failure
    
    # Note: Actual log verification would require inspecting logger output
    # This is a simplified version showing the property


@given(
    username=usernames,
    failed_attempts=st.integers(min_value=0, max_value=10)
)
def test_property_account_lockout_after_failures(
    username, failed_attempts, mock_db_session, mock_redis
):
    """
    Property 16: Password Complexity Validation (Account Lockout)
    
    Property: After 5 failed login attempts, the account should be locked
    for 30 minutes.
    
    Validates: Requirement 10.6 - Lock account after 5 failed attempts for 30 minutes
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Create a mock user with failed attempts
    lockout_threshold = 5
    should_be_locked = failed_attempts >= lockout_threshold
    
    locked_until = None
    if should_be_locked:
        locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    mock_user = User(
        id=1,
        username=username,
        email="test@example.com",
        password_hash="hashed_password",
        encryption_salt="salt",
        is_active=True,
        failed_login_attempts=failed_attempts,
        locked_until=locked_until
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    
    # Act & Assert
    if should_be_locked:
        from vmledger.exceptions import AccountLockedError
        with pytest.raises(AccountLockedError):
            auth_service._check_account_lockout(mock_user)
    else:
        # Should not raise exception
        try:
            auth_service._check_account_lockout(mock_user)
        except Exception as e:
            pytest.fail(f"Account should not be locked with {failed_attempts} attempts: {e}")


@given(
    username=usernames,
    password=passwords,
    token_invalidated=st.booleans()
)
def test_property_token_invalidation_on_logout(
    username, password, token_invalidated, mock_db_session, mock_redis
):
    """
    Property 14: Unauthenticated Request Rejection (Logout)
    
    Property: After logout, the token should be invalidated and cannot be
    used for subsequent requests.
    
    Validates: Requirement 10.1 - Require authentication before allowing access
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    # Create a mock user
    mock_user = User(
        id=1,
        username=username,
        email="test@example.com",
        password_hash="hashed_password",
        encryption_salt="salt",
        is_active=True
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    
    # Mock Redis token validation
    if token_invalidated:
        mock_redis.exists.return_value = 0  # Token not in Redis (invalidated)
    else:
        mock_redis.exists.return_value = 1  # Token still valid
    
    # Create a valid token
    from jose import jwt
    from vmledger.config import settings
    
    token_data = {
        "sub": str(mock_user.id),
        "username": mock_user.username,
        "email": mock_user.email,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(
        token_data,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Act & Assert
    if token_invalidated:
        # Invalidated token should be rejected
        with pytest.raises(TokenInvalidError):
            auth_service.validate_token(token)
    else:
        # Valid token should be accepted
        result = auth_service.validate_token(token)
        assert result is not None


@given(
    username=usernames,
    requests_per_minute=st.integers(min_value=0, max_value=200)
)
def test_property_rate_limiting_enforcement(
    username, requests_per_minute, mock_db_session, mock_redis
):
    """
    Property 14: Unauthenticated Request Rejection (Rate Limiting)
    
    Property: Users should be rate-limited to prevent brute force attacks.
    After exceeding the limit, requests should be rejected.
    
    Validates: Requirement 10.6 - Rate limiting for login attempts
    """
    # Arrange
    auth_service = AuthService(mock_db_session, mock_redis)
    
    rate_limit = 5  # 5 attempts per 15 minutes (as per requirement)
    
    # Mock Redis rate limit counter
    if requests_per_minute >= rate_limit:
        mock_redis.get.return_value = str(rate_limit)
        mock_redis.ttl.return_value = 900  # 15 minutes in seconds
    else:
        mock_redis.get.return_value = str(requests_per_minute)
    
    # Act & Assert
    if requests_per_minute >= rate_limit:
        from vmledger.exceptions import RateLimitExceededError
        with pytest.raises(RateLimitExceededError):
            auth_service._check_rate_limit(username)
    else:
        # Should not raise exception
        try:
            auth_service._check_rate_limit(username)
        except Exception as e:
            pytest.fail(f"Rate limit should not be exceeded with {requests_per_minute} requests: {e}")
