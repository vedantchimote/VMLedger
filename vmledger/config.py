"""
Configuration management using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = Field(default="VMLedger", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://vmledger:password@localhost:5432/vmledger",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = Field(default=5, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Database max overflow connections")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_password: str = Field(default="", description="Redis password")
    
    # Security Settings
    secret_key: str = Field(..., description="Secret key for JWT signing")
    encryption_master_key: str = Field(..., description="Master key for credential encryption")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT token expiration in hours")
    
    # Authentication Settings
    password_min_length: int = Field(default=12, description="Minimum password length")
    max_login_attempts: int = Field(default=5, description="Max failed login attempts before lockout")
    account_lockout_minutes: int = Field(default=30, description="Account lockout duration in minutes")
    rate_limit_per_minute: int = Field(default=100, description="API rate limit per user per minute")
    
    # Monitoring Settings
    ping_interval_seconds: int = Field(default=60, description="Ping check interval in seconds")
    metrics_interval_seconds: int = Field(default=300, description="Metrics collection interval in seconds")
    alert_cooldown_minutes: int = Field(default=15, description="Alert cooldown period in minutes")
    concurrent_workers: int = Field(default=10, description="Number of concurrent Celery workers")
    
    # SSH Settings
    ssh_connection_timeout: int = Field(default=10, description="SSH connection timeout in seconds")
    ssh_command_timeout: int = Field(default=30, description="SSH command execution timeout in seconds")
    ssh_max_retries: int = Field(default=3, description="Maximum SSH retry attempts")
    ssh_retry_delay: int = Field(default=5, description="Delay between SSH retries in seconds")
    
    # Data Retention
    ping_results_retention: int = Field(default=100, description="Number of ping results to retain per VM")
    metrics_retention: int = Field(default=1000, description="Number of metric records to retain per VM")
    alerts_retention_days: int = Field(default=90, description="Number of days to retain alert history")
    
    # Logging
    log_file_path: str = Field(default="logs/vmledger.log", description="Log file path")
    log_max_size_mb: int = Field(default=100, description="Maximum log file size in MB")
    log_retention_days: int = Field(default=30, description="Log retention period in days")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    # Email Settings (Optional)
    smtp_host: str = Field(default="", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_from_email: str = Field(default="noreply@vmledger.local", description="From email address")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")
    
    # CORS Settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @validator("jwt_algorithm")
    def validate_jwt_algorithm(cls, v):
        """Validate JWT algorithm is supported."""
        valid_algorithms = ["HS256", "HS384", "HS512"]
        if v not in valid_algorithms:
            raise ValueError(f"jwt_algorithm must be one of {valid_algorithms}")
        return v
    
    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format is valid."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"log_format must be one of {valid_formats}")
        return v.lower()


# Global settings instance
settings = Settings()


def validate_required_settings():
    """
    Validate that all required settings are properly configured.
    Raises ValueError if any required settings are missing or invalid.
    
    This function performs comprehensive validation of all environment variables
    to ensure the application can start safely and securely.
    
    Validates:
    - Requirements 15.1-15.6: Configuration management
    - Requirements 10.1-10.6: Authentication settings
    - Requirements 2.1-2.2: Credential encryption
    - Requirements 13.4: Database configuration
    """
    errors = []
    warnings = []
    
    # ===== CRITICAL SECURITY SETTINGS =====
    
    # Check secret key (Requirement 10.3)
    if not settings.secret_key:
        errors.append("SECRET_KEY is required but not set")
    elif settings.secret_key == "your-secret-key-here-change-in-production":
        errors.append("SECRET_KEY must be changed from default value")
    elif len(settings.secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters long")
    
    # Check encryption master key (Requirements 2.1, 2.2)
    if not settings.encryption_master_key:
        errors.append("ENCRYPTION_MASTER_KEY is required but not set")
    elif settings.encryption_master_key == "your-encryption-master-key-here-change-in-production":
        errors.append("ENCRYPTION_MASTER_KEY must be changed from default value")
    elif len(settings.encryption_master_key) < 32:
        errors.append("ENCRYPTION_MASTER_KEY must be at least 32 characters long")
    
    # ===== DATABASE CONFIGURATION =====
    
    # Check database URL (Requirement 13.4)
    if not settings.database_url:
        errors.append("DATABASE_URL is required but not set")
    elif not settings.database_url.startswith("postgresql://"):
        errors.append("DATABASE_URL must be a valid PostgreSQL connection string")
    elif "password@" in settings.database_url.lower():
        warnings.append("DATABASE_URL appears to contain default password - ensure this is changed in production")
    
    # Validate database pool settings
    if settings.database_pool_size < 1:
        errors.append("DATABASE_POOL_SIZE must be at least 1")
    if settings.database_max_overflow < 0:
        errors.append("DATABASE_MAX_OVERFLOW must be non-negative")
    
    # ===== REDIS CONFIGURATION =====
    
    # Check Redis URL
    if not settings.redis_url:
        errors.append("REDIS_URL is required but not set")
    elif not settings.redis_url.startswith("redis://"):
        errors.append("REDIS_URL must be a valid Redis connection string")
    
    # Warn if Redis password not set in production
    if not settings.debug and not settings.redis_password:
        warnings.append("REDIS_PASSWORD is not set - recommended for production environments")
    
    # ===== AUTHENTICATION SETTINGS =====
    
    # Validate password requirements (Requirement 10.5)
    if settings.password_min_length < 8:
        errors.append("PASSWORD_MIN_LENGTH must be at least 8 characters")
    elif settings.password_min_length > 128:
        errors.append("PASSWORD_MIN_LENGTH cannot exceed 128 characters")
    
    # Validate login attempt limits (Requirement 10.6)
    if settings.max_login_attempts < 3:
        errors.append("MAX_LOGIN_ATTEMPTS must be at least 3")
    elif settings.max_login_attempts > 10:
        warnings.append("MAX_LOGIN_ATTEMPTS is very high - consider lowering for better security")
    
    # Validate account lockout duration (Requirement 10.6)
    if settings.account_lockout_minutes < 5:
        errors.append("ACCOUNT_LOCKOUT_MINUTES must be at least 5")
    elif settings.account_lockout_minutes > 1440:
        errors.append("ACCOUNT_LOCKOUT_MINUTES cannot exceed 1440 (24 hours)")
    
    # Validate JWT settings (Requirements 10.3, 10.4)
    if settings.jwt_expiration_hours < 1:
        errors.append("JWT_EXPIRATION_HOURS must be at least 1")
    elif settings.jwt_expiration_hours > 168:
        warnings.append("JWT_EXPIRATION_HOURS is very long (>7 days) - consider shorter expiration for security")
    
    # ===== MONITORING SETTINGS =====
    
    # Validate ping interval (Requirements 4.1, 15.1)
    if settings.ping_interval_seconds < 10:
        errors.append("PING_INTERVAL_SECONDS must be at least 10 seconds")
    elif settings.ping_interval_seconds > 3600:
        warnings.append("PING_INTERVAL_SECONDS is very long (>1 hour) - VMs may be unreachable for extended periods")
    
    # Validate metrics interval (Requirements 5.6, 15.2)
    if settings.metrics_interval_seconds < 60:
        errors.append("METRICS_INTERVAL_SECONDS must be at least 60 seconds")
    elif settings.metrics_interval_seconds > 3600:
        warnings.append("METRICS_INTERVAL_SECONDS is very long (>1 hour) - metrics may be stale")
    
    # Validate alert cooldown (Requirements 8.5, 15.3)
    if settings.alert_cooldown_minutes < 1:
        errors.append("ALERT_COOLDOWN_MINUTES must be at least 1")
    elif settings.alert_cooldown_minutes > 1440:
        errors.append("ALERT_COOLDOWN_MINUTES cannot exceed 1440 (24 hours)")
    
    # Validate concurrent workers (Requirements 9.1-9.5, 15.4)
    if settings.concurrent_workers < 1:
        errors.append("CONCURRENT_WORKERS must be at least 1")
    elif settings.concurrent_workers > 100:
        warnings.append("CONCURRENT_WORKERS is very high (>100) - ensure system has sufficient resources")
    
    # ===== SSH SETTINGS =====
    
    # Validate SSH timeouts (Requirements 5.1-5.5)
    if settings.ssh_connection_timeout < 5:
        errors.append("SSH_CONNECTION_TIMEOUT must be at least 5 seconds")
    elif settings.ssh_connection_timeout > 60:
        warnings.append("SSH_CONNECTION_TIMEOUT is very long (>60s) - may cause slow monitoring")
    
    if settings.ssh_command_timeout < 10:
        errors.append("SSH_COMMAND_TIMEOUT must be at least 10 seconds")
    elif settings.ssh_command_timeout > 120:
        warnings.append("SSH_COMMAND_TIMEOUT is very long (>120s) - may cause slow monitoring")
    
    # Validate SSH retry settings (Requirement 5.5)
    if settings.ssh_max_retries < 1:
        errors.append("SSH_MAX_RETRIES must be at least 1")
    elif settings.ssh_max_retries > 10:
        warnings.append("SSH_MAX_RETRIES is very high (>10) - may cause excessive delays")
    
    if settings.ssh_retry_delay < 1:
        errors.append("SSH_RETRY_DELAY must be at least 1 second")
    elif settings.ssh_retry_delay > 60:
        warnings.append("SSH_RETRY_DELAY is very long (>60s) - may cause slow monitoring")
    
    # ===== DATA RETENTION =====
    
    # Validate ping results retention (Requirement 4.6)
    if settings.ping_results_retention < 10:
        errors.append("PING_RESULTS_RETENTION must be at least 10")
    elif settings.ping_results_retention > 10000:
        warnings.append("PING_RESULTS_RETENTION is very high (>10000) - may impact database performance")
    
    # Validate metrics retention (Requirement 5.7)
    if settings.metrics_retention < 100:
        errors.append("METRICS_RETENTION must be at least 100")
    elif settings.metrics_retention > 100000:
        warnings.append("METRICS_RETENTION is very high (>100000) - may impact database performance")
    
    # Validate alerts retention (Requirements 8.1-8.7)
    if settings.alerts_retention_days < 7:
        errors.append("ALERTS_RETENTION_DAYS must be at least 7")
    elif settings.alerts_retention_days > 365:
        warnings.append("ALERTS_RETENTION_DAYS is very long (>365 days) - may impact database performance")
    
    # ===== LOGGING SETTINGS =====
    
    # Validate log settings (Requirements 14.1-14.6)
    if settings.log_max_size_mb < 10:
        errors.append("LOG_MAX_SIZE_MB must be at least 10")
    elif settings.log_max_size_mb > 1000:
        warnings.append("LOG_MAX_SIZE_MB is very large (>1000MB) - may cause disk space issues")
    
    if settings.log_retention_days < 7:
        errors.append("LOG_RETENTION_DAYS must be at least 7")
    elif settings.log_retention_days > 365:
        warnings.append("LOG_RETENTION_DAYS is very long (>365 days) - may cause disk space issues")
    
    # ===== API SETTINGS =====
    
    # Validate API port
    if settings.api_port < 1 or settings.api_port > 65535:
        errors.append("API_PORT must be between 1 and 65535")
    
    # Validate API workers
    if settings.api_workers < 1:
        errors.append("API_WORKERS must be at least 1")
    elif settings.api_workers > 32:
        warnings.append("API_WORKERS is very high (>32) - ensure system has sufficient resources")
    
    # Validate rate limiting (Requirements 13.1-13.3)
    if settings.rate_limit_per_minute < 10:
        errors.append("RATE_LIMIT_PER_MINUTE must be at least 10")
    elif settings.rate_limit_per_minute > 1000:
        warnings.append("RATE_LIMIT_PER_MINUTE is very high (>1000) - may not provide effective rate limiting")
    
    # ===== PRODUCTION WARNINGS =====
    
    if not settings.debug:
        # Production-specific warnings
        if settings.cors_origins == "http://localhost:3000,http://localhost:8000":
            warnings.append("CORS_ORIGINS contains localhost - update with production frontend URL")
        
        if "localhost" in settings.database_url:
            warnings.append("DATABASE_URL points to localhost - ensure this is correct for production")
        
        if "localhost" in settings.redis_url:
            warnings.append("REDIS_URL points to localhost - ensure this is correct for production")
    
    # ===== REPORT RESULTS =====
    
    if errors:
        error_message = "Configuration validation failed:\n" + "\n".join(f"  - ERROR: {error}" for error in errors)
        if warnings:
            error_message += "\n\nWarnings:\n" + "\n".join(f"  - WARNING: {warning}" for warning in warnings)
        raise ValueError(error_message)
    
    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Configuration validation warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
