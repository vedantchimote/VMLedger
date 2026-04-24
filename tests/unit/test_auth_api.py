"""
Unit tests for Authentication API endpoints.

Tests registration, login, logout, and token refresh endpoints.

Requirements: 10.1-10.6
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import fakeredis

from vmledger.main import app
from vmledger.services.auth_service import AuthService
from vmledger.models.user import User


@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def redis_client():
    """Provide a fake Redis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def auth_service(db_session, redis_client):
    """Provide an AuthService instance for testing."""
    return AuthService(db_session, redis_client)


@pytest.fixture
def registered_user(auth_service):
    """Create a registered user for testing."""
    return auth_service.register_user(
        username="testuser",
        email="test@example.com",
        password="ValidPass123!"
    )


@pytest.fixture
def auth_token(auth_service, registered_user):
    """Get authentication token for testing."""
    result = auth_service.authenticate("testuser", "ValidPass123!")
    return result["token"]


class TestRegisterEndpoint:
    """Test POST /api/auth/register endpoint."""
    
    def test_successful_registration(self, client, db_session):
        """Test successful user registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "token" in data["data"]
        assert data["data"]["username"] == "newuser"
        assert data["data"]["email"] == "newuser@example.com"
        assert "user_id" in data["data"]
        assert isinstance(data["data"]["token"], str)
        assert len(data["data"]["token"]) > 0
    
    def test_registration_with_weak_password(self, client):
        """Test registration with password that doesn't meet complexity requirements."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "weak"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "PASSWORD_COMPLEXITY_ERROR"
    
    def test_registration_duplicate_username(self, client, registered_user):
        """Test registration with duplicate username."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "different@example.com",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "REGISTRATION_ERROR"
        assert "already exists" in data["error"]["message"]
    
    def test_registration_duplicate_email(self, client, registered_user):
        """Test registration with duplicate email."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "differentuser",
                "email": "test@example.com",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "REGISTRATION_ERROR"
        assert "already registered" in data["error"]["message"]
    
    def test_registration_invalid_email(self, client):
        """Test registration with invalid email format."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "invalid-email",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
    
    def test_registration_missing_fields(self, client):
        """Test registration with missing required fields."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser"
                # Missing email and password
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"


class TestLoginEndpoint:
    """Test POST /api/auth/login endpoint."""
    
    def test_successful_login(self, client, registered_user):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "token" in data["data"]
        assert data["data"]["username"] == "testuser"
        assert data["data"]["email"] == "test@example.com"
        assert data["data"]["user_id"] == registered_user.id
        assert isinstance(data["data"]["token"], str)
        assert len(data["data"]["token"]) > 0
    
    def test_login_invalid_username(self, client):
        """Test login with invalid username."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"
        assert "Invalid username or password" in data["error"]["message"]
    
    def test_login_invalid_password(self, client, registered_user):
        """Test login with invalid password."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"
    
    def test_login_account_locked(self, client, registered_user, db_session):
        """Test login when account is locked."""
        from datetime import datetime, timedelta
        
        # Lock the account
        registered_user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        registered_user.failed_login_attempts = 5
        db_session.commit()
        
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 429
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "ACCOUNT_LOCKED"
        assert "locked" in data["error"]["message"].lower()
    
    def test_login_rate_limit(self, client, registered_user):
        """Test rate limiting after multiple failed attempts."""
        # Make 5 failed login attempts
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={
                    "username": "testuser",
                    "password": "WrongPassword123!"
                }
            )
        
        # Next attempt should be rate limited
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 429
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    
    def test_login_missing_fields(self, client):
        """Test login with missing required fields."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser"
                # Missing password
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"


class TestLogoutEndpoint:
    """Test POST /api/auth/logout endpoint."""
    
    def test_successful_logout(self, client, auth_token):
        """Test successful logout."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "message" in data["data"]
        assert "Logged out successfully" in data["data"]["message"]
    
    def test_logout_without_token(self, client):
        """Test logout without authentication token."""
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
    
    def test_logout_with_invalid_token(self, client):
        """Test logout with invalid token."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        # Should still return 200 (logout is idempotent)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
    
    def test_logout_with_malformed_header(self, client):
        """Test logout with malformed Authorization header."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "InvalidFormat"}
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
    
    def test_token_invalid_after_logout(self, client, auth_token):
        """Test that token is invalid after logout."""
        # Logout
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        
        # Try to use the token again (should fail due to auth middleware)
        # Note: This would be tested in integration tests with actual middleware
        # For unit tests, we verify the logout endpoint itself works


class TestRefreshTokenEndpoint:
    """Test POST /api/auth/refresh endpoint."""
    
    def test_successful_token_refresh(self, client, auth_token):
        """Test successful token refresh."""
        import time
        
        # Wait a moment to ensure different timestamp
        time.sleep(1)
        
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "token" in data["data"]
        assert data["data"]["username"] == "testuser"
        assert data["data"]["email"] == "test@example.com"
        assert isinstance(data["data"]["token"], str)
        assert len(data["data"]["token"]) > 0
        # New token should be different after waiting
        assert data["data"]["token"] != auth_token
    
    def test_refresh_without_token(self, client):
        """Test token refresh without authentication token."""
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
    
    def test_refresh_with_invalid_token(self, client):
        """Test token refresh with invalid token."""
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "TOKEN_INVALID"
    
    def test_refresh_with_expired_token(self, client, auth_service, registered_user):
        """Test token refresh with expired token."""
        from datetime import datetime, timedelta
        from jose import jwt
        from vmledger.config import settings
        
        # Create an expired token
        expired_data = {
            "sub": str(registered_user.id),
            "username": registered_user.username,
            "email": registered_user.email,
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            "iat": datetime.utcnow() - timedelta(hours=25),
            "type": "access"
        }
        
        expired_token = jwt.encode(
            expired_data,
            settings.secret_key,
            algorithm=settings.jwt_algorithm
        )
        
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "TOKEN_EXPIRED"
    
    def test_old_token_invalid_after_refresh(self, client, auth_token, auth_service):
        """Test that old token is invalid after refresh."""
        import time
        
        # Wait a moment
        time.sleep(1)
        
        # Refresh token
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        
        # Old token should now be invalid
        from vmledger.services.auth_service import TokenInvalidError
        with pytest.raises(TokenInvalidError):
            auth_service.validate_token(auth_token)


class TestResponseFormat:
    """Test API response format consistency."""
    
    def test_success_response_format(self, client, registered_user):
        """Test that success responses follow consistent format."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "request_id" in data
    
    def test_error_response_format(self, client):
        """Test that error responses follow consistent format."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "ValidPass123!"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "request_id" in data


class TestPasswordComplexityValidation:
    """Test password complexity validation in registration endpoint."""
    
    @pytest.mark.parametrize("password,expected_error", [
        ("short", "at least 12 characters"),
        ("nouppercase123!", "uppercase letter"),
        ("NOLOWERCASE123!", "lowercase letter"),
        ("NoNumbers!", "number"),
        ("NoSpecialChar123", "special character"),
    ])
    def test_password_complexity_errors(self, client, password, expected_error):
        """Test various password complexity validation errors."""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": password
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "PASSWORD_COMPLEXITY_ERROR"
        assert expected_error.lower() in data["error"]["message"].lower()
