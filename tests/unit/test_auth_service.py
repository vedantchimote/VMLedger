"""
Unit tests for AuthService.

Tests authentication, authorization, password complexity validation,
token management, rate limiting, and account lockout.

Requirements: 10.1-10.6, 14.4
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import fakeredis

from vmledger.services.auth_service import (
    AuthService,
    AuthServiceError,
    PasswordComplexityError,
    AuthenticationError,
    AccountLockedError,
    TokenExpiredError,
    TokenInvalidError,
    RateLimitExceededError,
)
from vmledger.models.user import User


@pytest.fixture
def redis_client():
    """Provide a fake Redis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def auth_service(db_session, redis_client):
    """Provide an AuthService instance for testing."""
    return AuthService(db_session, redis_client)


class TestPasswordComplexity:
    """Test password complexity validation."""
    
    def test_valid_password(self, auth_service):
        """Test that valid password passes validation."""
        # Should not raise exception
        auth_service._validate_password_complexity("ValidPass123!")
    
    def test_password_too_short(self, auth_service):
        """Test that password shorter than 12 characters is rejected."""
        with pytest.raises(PasswordComplexityError, match="at least 12 characters"):
            auth_service._validate_password_complexity("Short1!")
    
    def test_password_no_uppercase(self, auth_service):
        """Test that password without uppercase letter is rejected."""
        with pytest.raises(PasswordComplexityError, match="uppercase letter"):
            auth_service._validate_password_complexity("validpass123!")
    
    def test_password_no_lowercase(self, auth_service):
        """Test that password without lowercase letter is rejected."""
        with pytest.raises(PasswordComplexityError, match="lowercase letter"):
            auth_service._validate_password_complexity("VALIDPASS123!")
    
    def test_password_no_number(self, auth_service):
        """Test that password without number is rejected."""
        with pytest.raises(PasswordComplexityError, match="number"):
            auth_service._validate_password_complexity("ValidPassword!")
    
    def test_password_no_special_char(self, auth_service):
        """Test that password without special character is rejected."""
        with pytest.raises(PasswordComplexityError, match="special character"):
            auth_service._validate_password_complexity("ValidPass1234")


class TestUserRegistration:
    """Test user registration functionality."""
    
    def test_successful_registration(self, auth_service, db_session):
        """Test successful user registration."""
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash is not None
        assert user.password_hash != "ValidPass123!"  # Password should be hashed
        assert user.encryption_salt is not None
        assert len(user.encryption_salt) == 64  # 32 bytes = 64 hex chars
        assert user.is_active is True
        assert user.failed_login_attempts == 0
    
    def test_registration_with_weak_password(self, auth_service):
        """Test that registration with weak password fails."""
        with pytest.raises(PasswordComplexityError):
            auth_service.register_user(
                username="testuser",
                email="test@example.com",
                password="weak"
            )
    
    def test_registration_duplicate_username(self, auth_service, db_session):
        """Test that duplicate username is rejected."""
        # Register first user
        auth_service.register_user(
            username="testuser",
            email="test1@example.com",
            password="ValidPass123!"
        )
        
        # Try to register with same username
        with pytest.raises(AuthServiceError, match="already exists"):
            auth_service.register_user(
                username="testuser",
                email="test2@example.com",
                password="ValidPass123!"
            )
    
    def test_registration_duplicate_email(self, auth_service, db_session):
        """Test that duplicate email is rejected."""
        # Register first user
        auth_service.register_user(
            username="testuser1",
            email="test@example.com",
            password="ValidPass123!"
        )
        
        # Try to register with same email
        with pytest.raises(AuthServiceError, match="already registered"):
            auth_service.register_user(
                username="testuser2",
                email="test@example.com",
                password="ValidPass123!"
            )


class TestAuthentication:
    """Test user authentication functionality."""
    
    @pytest.fixture
    def registered_user(self, auth_service):
        """Create a registered user for testing."""
        return auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
    
    def test_successful_authentication(self, auth_service, registered_user):
        """Test successful authentication."""
        result = auth_service.authenticate("testuser", "ValidPass123!")
        
        assert "token" in result
        assert result["user_id"] == registered_user.id
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert isinstance(result["token"], str)
        assert len(result["token"]) > 0
    
    def test_authentication_invalid_username(self, auth_service, registered_user):
        """Test authentication with invalid username."""
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            auth_service.authenticate("nonexistent", "ValidPass123!")
    
    def test_authentication_invalid_password(self, auth_service, registered_user):
        """Test authentication with invalid password."""
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            auth_service.authenticate("testuser", "WrongPassword123!")
    
    def test_authentication_resets_failed_attempts(self, auth_service, registered_user, db_session):
        """Test that successful authentication resets failed attempts counter."""
        # Manually set failed attempts
        registered_user.failed_login_attempts = 3
        db_session.commit()
        
        # Successful authentication
        auth_service.authenticate("testuser", "ValidPass123!")
        
        # Refresh user from database
        db_session.refresh(registered_user)
        
        assert registered_user.failed_login_attempts == 0
        assert registered_user.locked_until is None


class TestAccountLockout:
    """Test account lockout after failed login attempts."""
    
    @pytest.fixture
    def registered_user(self, auth_service):
        """Create a registered user for testing."""
        return auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
    
    def test_account_lockout_after_max_attempts(self, auth_service, registered_user, db_session):
        """Test that account is locked after max failed attempts."""
        # Make 5 failed login attempts
        for i in range(5):
            with pytest.raises(AuthenticationError):
                auth_service.authenticate("testuser", "WrongPassword123!")
        
        # Refresh user from database
        db_session.refresh(registered_user)
        
        assert registered_user.failed_login_attempts == 5
        assert registered_user.locked_until is not None
        assert registered_user.locked_until > datetime.utcnow()
    
    def test_authentication_fails_when_locked(self, auth_service, registered_user, db_session):
        """Test that authentication fails when account is locked."""
        # Lock the account
        registered_user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        registered_user.failed_login_attempts = 5
        db_session.commit()
        
        # Try to authenticate with correct password
        with pytest.raises(AccountLockedError, match="Account is locked"):
            auth_service.authenticate("testuser", "ValidPass123!")
    
    def test_lockout_expires_after_duration(self, auth_service, registered_user, db_session):
        """Test that lockout expires after configured duration."""
        # Lock the account with expired time
        registered_user.locked_until = datetime.utcnow() - timedelta(minutes=1)
        registered_user.failed_login_attempts = 5
        db_session.commit()
        
        # Should be able to authenticate now
        result = auth_service.authenticate("testuser", "ValidPass123!")
        
        assert "token" in result
        
        # Refresh user from database
        db_session.refresh(registered_user)
        
        # Lockout should be cleared
        assert registered_user.locked_until is None
        assert registered_user.failed_login_attempts == 0


class TestTokenManagement:
    """Test JWT token generation, validation, and management."""
    
    @pytest.fixture
    def registered_user(self, auth_service):
        """Create a registered user for testing."""
        return auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
    
    @pytest.fixture
    def auth_token(self, auth_service, registered_user):
        """Get authentication token for testing."""
        result = auth_service.authenticate("testuser", "ValidPass123!")
        return result["token"]
    
    def test_validate_valid_token(self, auth_service, auth_token, registered_user):
        """Test validation of valid token."""
        user = auth_service.validate_token(auth_token)
        
        assert user.id == registered_user.id
        assert user.username == "testuser"
        assert user.email == "test@example.com"
    
    def test_validate_invalid_token(self, auth_service):
        """Test validation of invalid token."""
        with pytest.raises(TokenInvalidError):
            auth_service.validate_token("invalid.token.here")
    
    def test_validate_token_after_logout(self, auth_service, auth_token):
        """Test that token is invalid after logout."""
        # Logout
        auth_service.logout(auth_token)
        
        # Token should now be invalid
        with pytest.raises(TokenInvalidError, match="invalidated"):
            auth_service.validate_token(auth_token)
    
    def test_refresh_token(self, auth_service, auth_token, registered_user):
        """Test token refresh functionality."""
        import time
        
        # Wait a moment to ensure different timestamp
        time.sleep(1)
        
        # Refresh token
        result = auth_service.refresh_token(auth_token)
        
        assert "token" in result
        assert result["token"] != auth_token  # New token should be different after waiting
        assert result["user_id"] == registered_user.id
        
        # Old token should be invalid
        with pytest.raises(TokenInvalidError):
            auth_service.validate_token(auth_token)
        
        # New token should be valid
        user = auth_service.validate_token(result["token"])
        assert user.id == registered_user.id
    
    def test_logout(self, auth_service, auth_token):
        """Test logout functionality."""
        # Logout should succeed
        result = auth_service.logout(auth_token)
        assert result is True
        
        # Token should be invalid after logout
        with pytest.raises(TokenInvalidError):
            auth_service.validate_token(auth_token)


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def registered_user(self, auth_service):
        """Create a registered user for testing."""
        return auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
    
    def test_rate_limit_after_max_attempts(self, auth_service, registered_user):
        """Test that rate limit is enforced after max attempts."""
        # Make 5 failed login attempts
        for i in range(5):
            with pytest.raises(AuthenticationError):
                auth_service.authenticate("testuser", "WrongPassword123!")
        
        # Next attempt should be rate limited
        with pytest.raises(RateLimitExceededError, match="Too many login attempts"):
            auth_service.authenticate("testuser", "WrongPassword123!")
    
    def test_rate_limit_reset_after_successful_login(self, auth_service, registered_user, redis_client):
        """Test that rate limit is reset after successful login."""
        # Make 2 failed attempts
        for i in range(2):
            with pytest.raises(AuthenticationError):
                auth_service.authenticate("testuser", "WrongPassword123!")
        
        # Successful login should reset rate limit
        auth_service.authenticate("testuser", "ValidPass123!")
        
        # Rate limit counter should be cleared
        key = "rate_limit:login:testuser"
        assert redis_client.get(key) is None


class TestAuthenticationLogging:
    """Test authentication attempt logging."""
    
    @pytest.fixture
    def registered_user(self, auth_service):
        """Create a registered user for testing."""
        return auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!"
        )
    
    def test_successful_login_logged(self, auth_service, registered_user, caplog):
        """Test that successful login is logged."""
        with caplog.at_level("INFO"):
            auth_service.authenticate("testuser", "ValidPass123!")
        
        # Check that success was logged
        assert any("Authentication successful" in record.message for record in caplog.records)
        assert any(record.levelname == "INFO" for record in caplog.records)
    
    def test_failed_login_logged(self, auth_service, registered_user, caplog):
        """Test that failed login is logged."""
        with caplog.at_level("WARNING"):
            with pytest.raises(AuthenticationError):
                auth_service.authenticate("testuser", "WrongPassword123!")
        
        # Check that failure was logged
        assert any("Authentication failed" in record.message for record in caplog.records)
        assert any(record.levelname == "WARNING" for record in caplog.records)


class TestPasswordHashing:
    """Test password hashing functionality."""
    
    def test_password_is_hashed(self, auth_service):
        """Test that password is hashed, not stored in plain text."""
        password = "ValidPass123!"
        hashed = auth_service._hash_password(password)
        
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt hash prefix
    
    def test_password_verification(self, auth_service):
        """Test password verification against hash."""
        password = "ValidPass123!"
        hashed = auth_service._hash_password(password)
        
        # Correct password should verify
        assert auth_service._verify_password(password, hashed) is True
        
        # Wrong password should not verify
        assert auth_service._verify_password("WrongPassword123!", hashed) is False
    
    def test_different_hashes_for_same_password(self, auth_service):
        """Test that same password produces different hashes (salt)."""
        password = "ValidPass123!"
        hash1 = auth_service._hash_password(password)
        hash2 = auth_service._hash_password(password)
        
        # Hashes should be different due to random salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert auth_service._verify_password(password, hash1) is True
        assert auth_service._verify_password(password, hash2) is True


class TestEncryptionSaltGeneration:
    """Test encryption salt generation for user credentials."""
    
    def test_salt_generation(self, auth_service):
        """Test that encryption salt is generated correctly."""
        salt = auth_service._generate_encryption_salt()
        
        assert isinstance(salt, str)
        assert len(salt) == 64  # 32 bytes = 64 hex characters
        
        # Should be valid hex
        int(salt, 16)  # Should not raise exception
    
    def test_unique_salts(self, auth_service):
        """Test that each salt is unique."""
        salt1 = auth_service._generate_encryption_salt()
        salt2 = auth_service._generate_encryption_salt()
        
        assert salt1 != salt2
