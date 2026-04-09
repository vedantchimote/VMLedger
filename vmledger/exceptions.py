"""
Centralized exception definitions for VMLedger.

This module provides structured exception classes for consistent error handling
across all services and API endpoints.

Requirements: 14.1-14.6
"""

from typing import Optional, Dict, Any


# Base Exception Classes

class VMLedgerError(Exception):
    """
    Base exception for all VMLedger errors.
    
    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        details: Additional error context
        http_status: HTTP status code for API responses
    """
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 500
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.details:
            error_dict["details"] = self.details
        return error_dict


# Validation Errors (HTTP 400)

class ValidationError(VMLedgerError):
    """
    Raised when input validation fails.
    
    HTTP Status: 400 Bad Request
    Requirements: 14.3
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraint: Optional[str] = None
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        if constraint:
            details["constraint"] = constraint
        
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            http_status=400
        )


class InvalidIPAddressError(ValidationError):
    """
    Raised when IP address format is invalid.
    
    Requirements: 1.2
    """
    
    def __init__(self, ip_address: str):
        super().__init__(
            message="Invalid IP address format",
            field="ip_address",
            value=ip_address,
            constraint="Must be valid IPv4 or IPv6 address"
        )


class InvalidSSHPortError(ValidationError):
    """
    Raised when SSH port is out of valid range.
    
    Requirements: 1.3
    """
    
    def __init__(self, port: int):
        super().__init__(
            message="SSH port must be between 1 and 65535",
            field="ssh_port",
            value=port,
            constraint="1 <= port <= 65535"
        )


class InvalidSSHKeyError(ValidationError):
    """
    Raised when SSH key format is invalid.
    
    Requirements: 2.5
    """
    
    def __init__(self, message: str = "Invalid SSH key format"):
        super().__init__(
            message=message,
            field="ssh_private_key",
            constraint="Must be valid RSA, ECDSA, or Ed25519 private key (DSA is deprecated)"
        )


class PasswordComplexityError(ValidationError):
    """
    Raised when password does not meet complexity requirements.
    
    Requirements: 10.5
    """
    
    def __init__(self, message: str = "Password does not meet complexity requirements"):
        super().__init__(
            message=message,
            field="password",
            constraint="Minimum 12 characters with uppercase, lowercase, number, and special character"
        )
        self.code = "PASSWORD_COMPLEXITY_ERROR"


class DeploymentNotesTooLongError(ValidationError):
    """
    Raised when deployment notes exceed maximum length.
    
    Requirements: 6.4
    """
    
    def __init__(self, length: int):
        super().__init__(
            message="Deployment notes exceed maximum length",
            field="deployment_notes",
            value=f"{length} characters",
            constraint="Maximum 50,000 characters"
        )


class DuplicateVMError(ValidationError):
    """
    Raised when attempting to register duplicate VM.
    
    Requirements: 1.6
    """
    
    def __init__(self, ip_address: str, ssh_port: int):
        super().__init__(
            message=f"VM with IP {ip_address} and port {ssh_port} already exists",
            constraint="IP address and SSH port combination must be unique per user"
        )
        self.code = "DUPLICATE_VM"


class MissingCredentialsError(ValidationError):
    """
    Raised when no credentials are provided for VM.
    """
    
    def __init__(self):
        super().__init__(
            message="At least one credential type (SSH key or password) is required",
            constraint="Provide either ssh_private_key or ssh_password"
        )


# Authentication/Authorization Errors (HTTP 401/403)

class AuthenticationError(VMLedgerError):
    """
    Raised when authentication fails.
    
    HTTP Status: 401 Unauthorized
    Requirements: 10.1, 10.2, 14.4
    """
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            http_status=401
        )


class InvalidCredentialsError(AuthenticationError):
    """
    Raised when username or password is incorrect.
    
    Requirements: 10.2
    """
    
    def __init__(self):
        super().__init__(message="Invalid username or password")


class TokenExpiredError(AuthenticationError):
    """
    Raised when session token has expired.
    
    Requirements: 10.4
    """
    
    def __init__(self, message: str = "Session token has expired. Please login again."):
        super().__init__(message=message)
        self.code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthenticationError):
    """
    Raised when session token is invalid or malformed.
    
    Requirements: 10.3
    """
    
    def __init__(self, message: str = "Invalid authentication token"):
        super().__init__(message=message)
        self.code = "TOKEN_INVALID"


class MissingAuthorizationHeaderError(AuthenticationError):
    """
    Raised when Authorization header is missing.
    
    Requirements: 10.1
    """
    
    def __init__(self):
        super().__init__(message="Missing Authorization header")
        self.code = "UNAUTHORIZED"


class InvalidAuthorizationHeaderError(AuthenticationError):
    """
    Raised when Authorization header format is invalid.
    
    Requirements: 10.1
    """
    
    def __init__(self):
        super().__init__(message="Invalid Authorization header format. Expected: Bearer <token>")
        self.code = "UNAUTHORIZED"


class AccountLockedError(VMLedgerError):
    """
    Raised when account is locked due to failed login attempts.
    
    HTTP Status: 429 Too Many Requests
    Requirements: 10.6
    """
    
    def __init__(self, locked_until: str):
        super().__init__(
            message=f"Account is locked due to too many failed login attempts. Try again after {locked_until}",
            code="ACCOUNT_LOCKED",
            details={"locked_until": locked_until},
            http_status=429
        )


class RateLimitExceededError(VMLedgerError):
    """
    Raised when rate limit is exceeded.
    
    HTTP Status: 429 Too Many Requests
    Requirements: 10.6
    """
    
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            http_status=429
        )


class UnauthorizedAccessError(VMLedgerError):
    """
    Raised when user attempts to access resource they don't own.
    
    HTTP Status: 403 Forbidden
    Requirements: 3.1-3.5
    """
    
    def __init__(self, resource_type: str = "resource", resource_id: Optional[int] = None):
        message = f"Access denied to {resource_type}"
        if resource_id:
            message += f" {resource_id}"
        
        super().__init__(
            message=message,
            code="FORBIDDEN",
            http_status=403
        )


class InsufficientPermissionsError(VMLedgerError):
    """
    Raised when user lacks required permissions.
    
    HTTP Status: 403 Forbidden
    """
    
    def __init__(self, action: str):
        super().__init__(
            message=f"Insufficient permissions to {action}",
            code="FORBIDDEN",
            http_status=403
        )


# Resource Not Found Errors (HTTP 404)

class ResourceNotFoundError(VMLedgerError):
    """
    Raised when requested resource does not exist.
    
    HTTP Status: 404 Not Found
    """
    
    def __init__(self, resource_type: str, resource_id: Optional[int] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        
        super().__init__(
            message=message,
            code=f"{resource_type.upper()}_NOT_FOUND",
            http_status=404
        )


class VMNotFoundError(ResourceNotFoundError):
    """
    Raised when VM does not exist.
    
    Requirements: 3.2, 3.3
    """
    
    def __init__(self, vm_id: int):
        super().__init__(resource_type="VM", resource_id=vm_id)


class UserNotFoundError(ResourceNotFoundError):
    """
    Raised when user does not exist.
    """
    
    def __init__(self, user_id: Optional[int] = None, username: Optional[str] = None):
        if username:
            super().__init__(resource_type="User")
            self.message = f"User not found: {username}"
        else:
            super().__init__(resource_type="User", resource_id=user_id)


# Service-Specific Errors (HTTP 500)

class ServiceError(VMLedgerError):
    """
    Base class for internal service errors.
    
    HTTP Status: 500 Internal Server Error
    Requirements: 14.3
    """
    
    def __init__(self, message: str, service: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            details=details or {},
            http_status=500
        )
        self.service = service


class DatabaseError(ServiceError):
    """
    Raised when database operation fails.
    
    Requirements: 14.3
    """
    
    def __init__(self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            service="database",
            details=details
        )
        self.code = "DATABASE_ERROR"


class SSHConnectionError(ServiceError):
    """
    Raised when SSH connection fails.
    
    Requirements: 5.5, 14.1
    """
    
    def __init__(self, vm_id: int, error_type: str, message: str):
        super().__init__(
            message=f"SSH connection failed: {message}",
            service="ssh",
            details={
                "vm_id": vm_id,
                "error_type": error_type
            }
        )
        self.code = "SSH_CONNECTION_ERROR"


class MetricCollectionError(ServiceError):
    """
    Raised when metric collection fails.
    
    Requirements: 5.5
    """
    
    def __init__(self, vm_id: int, message: str):
        super().__init__(
            message=f"Metric collection failed: {message}",
            service="metric_collector",
            details={"vm_id": vm_id}
        )
        self.code = "METRIC_COLLECTION_ERROR"


class AlertDeliveryError(ServiceError):
    """
    Raised when alert notification fails.
    
    Requirements: 8.2, 8.3
    """
    
    def __init__(self, vm_id: int, notification_method: str, message: str):
        super().__init__(
            message=f"Alert delivery failed: {message}",
            service="alert_handler",
            details={
                "vm_id": vm_id,
                "notification_method": notification_method
            }
        )
        self.code = "ALERT_DELIVERY_ERROR"


class EncryptionError(ServiceError):
    """
    Raised when encryption/decryption fails.
    
    Requirements: 2.1, 2.2
    """
    
    def __init__(self, message: str = "Encryption operation failed"):
        super().__init__(
            message=message,
            service="credential_manager"
        )
        self.code = "ENCRYPTION_ERROR"


class SearchError(ServiceError):
    """
    Raised when search operation fails.
    
    Requirements: 7.1-7.6
    """
    
    def __init__(self, message: str = "Search operation failed"):
        super().__init__(
            message=message,
            service="search_engine"
        )
        self.code = "SEARCH_ERROR"


# Legacy Exception Aliases (for backward compatibility)

class AuthServiceError(AuthenticationError):
    """Legacy alias for AuthenticationError."""
    pass


class VMRegistryError(ValidationError):
    """Legacy alias for ValidationError in VM registry context."""
    pass


class CredentialManagerError(ServiceError):
    """Legacy alias for ServiceError in credential manager context."""
    
    def __init__(self, message: str):
        super().__init__(message=message, service="credential_manager")


class HealthCheckServiceError(ServiceError):
    """Legacy alias for ServiceError in health check context."""
    
    def __init__(self, message: str):
        super().__init__(message=message, service="health_check")


class MetricCollectorServiceError(ServiceError):
    """Legacy alias for ServiceError in metric collector context."""
    
    def __init__(self, message: str):
        super().__init__(message=message, service="metric_collector")


class AlertHandlerServiceError(ServiceError):
    """Legacy alias for ServiceError in alert handler context."""
    
    def __init__(self, message: str):
        super().__init__(message=message, service="alert_handler")


class DataCleanupServiceError(ServiceError):
    """Legacy alias for ServiceError in data cleanup context."""
    
    def __init__(self, message: str):
        super().__init__(message=message, service="data_cleanup")
