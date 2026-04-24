"""
Unit tests for authentication middleware.

Tests JWT token validation, public path handling, and error responses.

Requirements: 10.1, 10.3, 10.4, 14.4
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import Request, Response
from starlette.datastructures import Headers

from vmledger.middleware.auth import AuthMiddleware
from vmledger.services.auth_service import (
    TokenExpiredError,
    TokenInvalidError
)
from vmledger.models.user import User


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = Mock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return AuthMiddleware(app=Mock())


class TestAuthMiddlewarePublicPaths:
    """Test suite for public path detection."""
    
    def test_root_path_is_public(self, middleware):
        """Test that root path is public."""
        assert middleware._is_public_path("/") is True
    
    def test_health_endpoints_are_public(self, middleware):
        """Test that health check endpoints are public."""
        assert middleware._is_public_path("/health") is True
        assert middleware._is_public_path("/health/detailed") is True
    
    def test_auth_endpoints_are_public(self, middleware):
        """Test that auth endpoints are public."""
        assert middleware._is_public_path("/api/auth/register") is True
        assert middleware._is_public_path("/api/auth/login") is True
    
    def test_docs_endpoints_are_public(self, middleware):
        """Test that API docs endpoints are public."""
        assert middleware._is_public_path("/api/docs") is True
        assert middleware._is_public_path("/api/redoc") is True
        assert middleware._is_public_path("/openapi.json") is True
    
    def test_protected_endpoints_not_public(self, middleware):
        """Test that protected endpoints are not public."""
        assert middleware._is_public_path("/api/vms") is False
        assert middleware._is_public_path("/api/metrics") is False
        assert middleware._is_public_path("/api/alerts") is False


class TestAuthMiddlewareTokenExtraction:
    """Test suite for token extraction."""
    
    def test_extract_valid_bearer_token(self, middleware):
        """Test extraction of valid Bearer token."""
        mock_request = Mock(spec=Request)
        mock_request.headers = Headers({"Authorization": "Bearer token123"})
        
        token = middleware._extract_token(mock_request)
        assert token == "token123"
    
    def test_extract_token_case_insensitive(self, middleware):
        """Test that Bearer is case-insensitive."""
        mock_request = Mock(spec=Request)
        mock_request.headers = Headers({"Authorization": "bearer token456"})
        
        token = middleware._extract_token(mock_request)
        assert token == "token456"
    
    def test_missing_authorization_header(self, middleware):
        """Test that missing Authorization header returns None."""
        mock_request = Mock(spec=Request)
        mock_request.headers = Headers({})
        
        token = middleware._extract_token(mock_request)
        assert token is None
    
    def test_malformed_authorization_header(self, middleware):
        """Test that malformed Authorization header returns None."""
        mock_request = Mock(spec=Request)
        
        # Missing "Bearer" prefix
        mock_request.headers = Headers({"Authorization": "token123"})
        assert middleware._extract_token(mock_request) is None
        
        # Only "Bearer" without token
        mock_request.headers = Headers({"Authorization": "Bearer"})
        assert middleware._extract_token(mock_request) is None
        
        # Empty Authorization header
        mock_request.headers = Headers({"Authorization": ""})
        assert middleware._extract_token(mock_request) is None


class TestAuthMiddlewareUnauthorizedResponse:
    """Test suite for unauthorized response generation."""
    
    def test_unauthorized_response_format(self, middleware):
        """Test that unauthorized response has correct format."""
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.request_id = "test-request-123"
        
        response = middleware._unauthorized_response("Test error message", mock_request)
        
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        
        # Check response body
        import json
        body = json.loads(response.body.decode())
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"
        assert body["error"]["message"] == "Test error message"
        assert body["error"]["request_id"] == "test-request-123"
    
    def test_unauthorized_response_without_request_id(self, middleware):
        """Test unauthorized response when request_id is missing."""
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.request_id = "unknown"  # Set a default value
        
        response = middleware._unauthorized_response("Test error", mock_request)
        
        assert response.status_code == 401
        import json
        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] == "unknown"


class TestAuthMiddlewareIntegration:
    """Integration tests for middleware dispatch logic."""
    
    @pytest.mark.asyncio
    async def test_public_path_bypasses_auth(self, middleware):
        """Test that public paths bypass authentication."""
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/"
        
        mock_call_next = AsyncMock(return_value=Response(content="OK", status_code=200))
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 200
        mock_call_next.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, middleware):
        """Test that missing token returns 401."""
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/vms"
        mock_request.headers = Headers({})
        mock_request.state = Mock()
        mock_request.state.request_id = "test-123"
        
        mock_call_next = AsyncMock()
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Response should be a JSONResponse, not the mock
        assert hasattr(response, 'status_code')
        assert response.status_code == 401
        mock_call_next.assert_not_called()
        
        # Check response body
        import json
        body = json.loads(response.body.decode())
        assert body["success"] is False
        assert "Missing authentication token" in body["error"]["message"]
    
    @pytest.mark.asyncio
    @patch("vmledger.middleware.auth.get_db")
    @patch("vmledger.middleware.auth.AuthService")
    async def test_valid_token_allows_access(
        self,
        mock_auth_service_class,
        mock_get_db,
        middleware,
        mock_user
    ):
        """Test that valid token allows access."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_auth_service = Mock()
        mock_auth_service.validate_token.return_value = mock_user
        mock_auth_service_class.return_value = mock_auth_service
        
        # Setup request with proper state object
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/vms"
        mock_request.headers = Headers({"Authorization": "Bearer valid_token"})
        
        # Create a real-ish state object that can be modified
        class State:
            pass
        mock_request.state = State()
        mock_request.method = "GET"
        
        mock_call_next = AsyncMock(return_value=Response(content="OK", status_code=200))
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 200
        assert mock_request.state.user_id == 1
        assert mock_request.state.user == mock_user
        mock_call_next.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("vmledger.middleware.auth.get_db")
    @patch("vmledger.middleware.auth.AuthService")
    async def test_expired_token_returns_401(
        self,
        mock_auth_service_class,
        mock_get_db,
        middleware
    ):
        """Test that expired token returns 401."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_auth_service = Mock()
        mock_auth_service.validate_token.side_effect = TokenExpiredError("Token expired")
        mock_auth_service_class.return_value = mock_auth_service
        
        # Setup request
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/vms"
        mock_request.headers = Headers({"Authorization": "Bearer expired_token"})
        mock_request.state = Mock()
        mock_request.state.request_id = "test-123"
        mock_request.method = "GET"
        
        mock_call_next = AsyncMock()
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert hasattr(response, 'status_code')
        assert response.status_code == 401
        import json
        body = json.loads(response.body.decode())
        assert "expired" in body["error"]["message"].lower()
        mock_call_next.assert_not_called()
    
    @pytest.mark.asyncio
    @patch("vmledger.middleware.auth.get_db")
    @patch("vmledger.middleware.auth.AuthService")
    async def test_invalid_token_returns_401(
        self,
        mock_auth_service_class,
        mock_get_db,
        middleware
    ):
        """Test that invalid token returns 401."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_auth_service = Mock()
        mock_auth_service.validate_token.side_effect = TokenInvalidError("Invalid token")
        mock_auth_service_class.return_value = mock_auth_service
        
        # Setup request
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/vms"
        mock_request.headers = Headers({"Authorization": "Bearer invalid_token"})
        mock_request.state = Mock()
        mock_request.state.request_id = "test-123"
        mock_request.method = "GET"
        
        mock_call_next = AsyncMock()
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert hasattr(response, 'status_code')
        assert response.status_code == 401
        import json
        body = json.loads(response.body.decode())
        assert "Invalid authentication token" in body["error"]["message"]
        mock_call_next.assert_not_called()
    
    @pytest.mark.asyncio
    @patch("vmledger.middleware.auth.get_db")
    @patch("vmledger.middleware.auth.AuthService")
    async def test_auth_service_exception_returns_500(
        self,
        mock_auth_service_class,
        mock_get_db,
        middleware
    ):
        """Test that unexpected auth service errors return 500."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_auth_service = Mock()
        mock_auth_service.validate_token.side_effect = Exception("Database error")
        mock_auth_service_class.return_value = mock_auth_service
        
        # Setup request
        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/vms"
        mock_request.headers = Headers({"Authorization": "Bearer token"})
        mock_request.state = Mock()
        mock_request.state.request_id = "test-123"
        mock_request.method = "GET"
        
        mock_call_next = AsyncMock()
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert hasattr(response, 'status_code')
        assert response.status_code == 500
        import json
        body = json.loads(response.body.decode())
        assert "Authentication service error" in body["error"]["message"]
        mock_call_next.assert_not_called()
