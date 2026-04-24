"""
Unit tests for centralized error handling.

This module tests the structured error handling system including custom
exceptions, error handlers, and response formatting.

Requirements: 14.1-14.6
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from vmledger.exceptions import (
    VMLedgerError,
    ValidationError,
    InvalidIPAddressError,
    InvalidSSHPortError,
    InvalidSSHKeyError,
    PasswordComplexityError,
    DuplicateVMError,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    AccountLockedError,
    RateLimitExceededError,
    UnauthorizedAccessError,
    VMNotFoundError,
    DatabaseError,
    SSHConnectionError,
    MetricCollectionError,
    AlertDeliveryError
)
from vmledger.error_handlers import register_exception_handlers


# Create test app
app = FastAPI()
register_exception_handlers(app)


# Test endpoints that raise different exceptions
@app.get("/test/validation-error")
async def test_validation_error():
    raise ValidationError("Test validation error", field="test_field", value="test_value")


@app.get("/test/invalid-ip")
async def test_invalid_ip():
    raise InvalidIPAddressError("invalid-ip")


@app.get("/test/invalid-port")
async def test_invalid_port():
    raise InvalidSSHPortError(99999)


@app.get("/test/invalid-ssh-key")
async def test_invalid_ssh_key():
    raise InvalidSSHKeyError()


@app.get("/test/password-complexity")
async def test_password_complexity():
    raise PasswordComplexityError()


@app.get("/test/duplicate-vm")
async def test_duplicate_vm():
    raise DuplicateVMError("192.168.1.1", 22)


@app.get("/test/authentication-error")
async def test_authentication_error():
    raise AuthenticationError()


@app.get("/test/invalid-credentials")
async def test_invalid_credentials():
    raise InvalidCredentialsError()


@app.get("/test/token-expired")
async def test_token_expired():
    raise TokenExpiredError()


@app.get("/test/token-invalid")
async def test_token_invalid():
    raise TokenInvalidError()


@app.get("/test/account-locked")
async def test_account_locked():
    raise AccountLockedError("2024-01-01T00:00:00Z")


@app.get("/test/rate-limit")
async def test_rate_limit():
    raise RateLimitExceededError()


@app.get("/test/unauthorized-access")
async def test_unauthorized_access():
    raise UnauthorizedAccessError("VM", 123)


@app.get("/test/vm-not-found")
async def test_vm_not_found():
    raise VMNotFoundError(123)


@app.get("/test/database-error")
async def test_database_error():
    raise DatabaseError()


@app.get("/test/ssh-connection-error")
async def test_ssh_connection_error():
    raise SSHConnectionError(123, "TIMEOUT", "Connection timed out")


@app.get("/test/metric-collection-error")
async def test_metric_collection_error():
    raise MetricCollectionError(123, "Failed to collect metrics")


@app.get("/test/alert-delivery-error")
async def test_alert_delivery_error():
    raise AlertDeliveryError(123, "webhook", "Webhook failed")


# Add request ID middleware for testing
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = "test-request-id"
    response = await call_next(request)
    return response


client = TestClient(app)


class TestValidationErrors:
    """Test validation error responses (HTTP 400)."""
    
    def test_validation_error_response(self):
        """Test generic validation error returns 400 with proper structure."""
        response = client.get("/test/validation-error")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Test validation error"
        assert "details" in data["error"]
        assert data["error"]["details"]["field"] == "test_field"
        assert data["request_id"] == "test-request-id"
    
    def test_invalid_ip_address_error(self):
        """Test invalid IP address error returns 400."""
        response = client.get("/test/invalid-ip")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "IP address" in data["error"]["message"]
        assert data["error"]["details"]["field"] == "ip_address"
    
    def test_invalid_ssh_port_error(self):
        """Test invalid SSH port error returns 400."""
        response = client.get("/test/invalid-port")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "SSH port" in data["error"]["message"]
        assert data["error"]["details"]["field"] == "ssh_port"
    
    def test_invalid_ssh_key_error(self):
        """Test invalid SSH key error returns 400."""
        response = client.get("/test/invalid-ssh-key")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "SSH key" in data["error"]["message"]
    
    def test_password_complexity_error(self):
        """Test password complexity error returns 400."""
        response = client.get("/test/password-complexity")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "password" in data["error"]["message"].lower()
    
    def test_duplicate_vm_error(self):
        """Test duplicate VM error returns 400."""
        response = client.get("/test/duplicate-vm")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"]["code"] == "DUPLICATE_VM"
        assert "192.168.1.1" in data["error"]["message"]


class TestAuthenticationErrors:
    """Test authentication/authorization error responses (HTTP 401/403)."""
    
    def test_authentication_error(self):
        """Test authentication error returns 401."""
        response = client.get("/test/authentication-error")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"
        assert data["request_id"] == "test-request-id"
    
    def test_invalid_credentials_error(self):
        """Test invalid credentials error returns 401."""
        response = client.get("/test/invalid-credentials")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"
    
    def test_token_expired_error(self):
        """Test token expired error returns 401."""
        response = client.get("/test/token-expired")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["error"]["code"] == "TOKEN_EXPIRED"
        assert "expired" in data["error"]["message"].lower()
    
    def test_token_invalid_error(self):
        """Test token invalid error returns 401."""
        response = client.get("/test/token-invalid")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["error"]["code"] == "TOKEN_INVALID"
    
    def test_account_locked_error(self):
        """Test account locked error returns 429."""
        response = client.get("/test/account-locked")
        
        assert response.status_code == 429
        data = response.json()
        
        assert data["error"]["code"] == "ACCOUNT_LOCKED"
        assert "locked" in data["error"]["message"].lower()
    
    def test_rate_limit_error(self):
        """Test rate limit error returns 429."""
        response = client.get("/test/rate-limit")
        
        assert response.status_code == 429
        data = response.json()
        
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    
    def test_unauthorized_access_error(self):
        """Test unauthorized access error returns 403."""
        response = client.get("/test/unauthorized-access")
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["error"]["code"] == "FORBIDDEN"
        assert "VM" in data["error"]["message"]


class TestResourceNotFoundErrors:
    """Test resource not found error responses (HTTP 404)."""
    
    def test_vm_not_found_error(self):
        """Test VM not found error returns 404."""
        response = client.get("/test/vm-not-found")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
        assert "123" in data["error"]["message"]
        assert data["request_id"] == "test-request-id"


class TestInternalErrors:
    """Test internal error responses (HTTP 500)."""
    
    def test_database_error(self):
        """Test database error returns 500."""
        response = client.get("/test/database-error")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "DATABASE_ERROR"
        assert data["request_id"] == "test-request-id"
    
    def test_ssh_connection_error(self):
        """Test SSH connection error returns 500."""
        response = client.get("/test/ssh-connection-error")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["error"]["code"] == "SSH_CONNECTION_ERROR"
        assert "details" in data["error"]
        assert data["error"]["details"]["vm_id"] == 123
    
    def test_metric_collection_error(self):
        """Test metric collection error returns 500."""
        response = client.get("/test/metric-collection-error")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["error"]["code"] == "METRIC_COLLECTION_ERROR"
    
    def test_alert_delivery_error(self):
        """Test alert delivery error returns 500."""
        response = client.get("/test/alert-delivery-error")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["error"]["code"] == "ALERT_DELIVERY_ERROR"


class TestErrorResponseStructure:
    """Test error response structure consistency."""
    
    def test_error_response_has_required_fields(self):
        """Test all error responses have required fields."""
        response = client.get("/test/validation-error")
        data = response.json()
        
        # Required top-level fields
        assert "success" in data
        assert "error" in data
        assert "request_id" in data
        
        # Required error fields
        assert "code" in data["error"]
        assert "message" in data["error"]
        
        # Success should always be False for errors
        assert data["success"] is False
    
    def test_request_id_in_all_errors(self):
        """Test request ID is included in all error responses."""
        endpoints = [
            "/test/validation-error",
            "/test/authentication-error",
            "/test/vm-not-found",
            "/test/database-error"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            data = response.json()
            assert data["request_id"] == "test-request-id"


class TestExceptionToDict:
    """Test exception to_dict() method."""
    
    def test_exception_to_dict_basic(self):
        """Test basic exception to_dict conversion."""
        exc = ValidationError("Test error", field="test")
        result = exc.to_dict()
        
        assert result["code"] == "VALIDATION_ERROR"
        assert result["message"] == "Test error"
        assert "details" in result
        assert result["details"]["field"] == "test"
    
    def test_exception_to_dict_no_details(self):
        """Test exception to_dict with no details."""
        exc = AuthenticationError("Auth failed")
        result = exc.to_dict()
        
        assert result["code"] == "AUTHENTICATION_FAILED"
        assert result["message"] == "Auth failed"
        assert "details" not in result or result.get("details") == {}
