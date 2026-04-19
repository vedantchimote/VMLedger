"""
Business logic services.
Services will be implemented in subsequent tasks.
"""

from vmledger.services.credential_manager import (
    CredentialManager,
    CredentialManagerError,
    InvalidSSHKeyError,
    DecryptionError,
)

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

from vmledger.services.vm_registry_service import (
    VMRegistryService,
    VMRegistryError,
    DuplicateVMError,
    VMNotFoundError,
    UnauthorizedAccessError,
)

from vmledger.services.health_check_service import (
    HealthCheckService,
    HealthCheckServiceError,
    PingResultData,
)

from vmledger.services.metric_collector_service import (
    MetricCollectorService,
    MetricCollectorServiceError,
    SSHConnectionError,
    CommandExecutionError,
    MetricData,
)

from vmledger.services.search_engine_service import (
    SearchEngineService,
    VMSearchResult,
    get_search_engine_service,
)

__all__ = [
    "CredentialManager",
    "CredentialManagerError",
    "InvalidSSHKeyError",
    "DecryptionError",
    "AuthService",
    "AuthServiceError",
    "PasswordComplexityError",
    "AuthenticationError",
    "AccountLockedError",
    "TokenExpiredError",
    "TokenInvalidError",
    "RateLimitExceededError",
    "VMRegistryService",
    "VMRegistryError",
    "DuplicateVMError",
    "VMNotFoundError",
    "UnauthorizedAccessError",
    "HealthCheckService",
    "HealthCheckServiceError",
    "PingResultData",
    "MetricCollectorService",
    "MetricCollectorServiceError",
    "SSHConnectionError",
    "CommandExecutionError",
    "MetricData",
    "SearchEngineService",
    "VMSearchResult",
    "get_search_engine_service",
]

# TODO: Implement services in future tasks
# - AlertHandlerService (Task 11)
