# Environment Variables Documentation

This document provides comprehensive documentation for all environment variables used in VMLedger.

## Table of Contents

- [Required Variables](#required-variables)
- [Application Settings](#application-settings)
- [API Settings](#api-settings)
- [Database Configuration](#database-configuration)
- [Redis Configuration](#redis-configuration)
- [Security Settings](#security-settings)
- [Authentication Settings](#authentication-settings)
- [Monitoring Settings](#monitoring-settings)
- [SSH Settings](#ssh-settings)
- [Data Retention](#data-retention)
- [Logging](#logging)
- [Email Settings](#email-settings)
- [CORS Settings](#cors-settings)

---

## Required Variables

These variables **MUST** be set before starting the application. The application will fail to start if these are not properly configured.

### SECRET_KEY

- **Type**: String
- **Required**: Yes
- **Default**: None
- **Description**: Secret key used for JWT token signing and session management. Must be a cryptographically secure random string.
- **Security**: CRITICAL - Never commit this value to version control
- **Generation**: 
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Example**: `xK8vN2mP9qR5sT7uW1yZ3aB4cD6eF8gH9jK0lM2nO4pQ6rS8tU0vW2xY4zA6bC8d`
- **Validates**: Requirements 10.1-10.4

### ENCRYPTION_MASTER_KEY

- **Type**: String
- **Required**: Yes
- **Default**: None
- **Description**: Master encryption key used for AES-256 encryption of SSH credentials and passwords. Must be a cryptographically secure random string.
- **Security**: CRITICAL - Never commit this value to version control. Loss of this key means all stored credentials become unrecoverable.
- **Generation**: 
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Example**: `aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7iJ8kL9mN0oP1q`
- **Validates**: Requirements 2.1, 2.2

### DATABASE_URL

- **Type**: String (PostgreSQL connection URL)
- **Required**: Yes
- **Default**: `postgresql://vmledger:password@localhost:5432/vmledger`
- **Description**: PostgreSQL database connection string
- **Format**: `postgresql://[user]:[password]@[host]:[port]/[database]`
- **Security**: Contains sensitive credentials - do not commit production values
- **Example**: `postgresql://vmledger:SecurePass123!@db.example.com:5432/vmledger_prod`
- **Validates**: Requirements 13.4

---

## Application Settings

### APP_NAME

- **Type**: String
- **Required**: No
- **Default**: `VMLedger`
- **Description**: Application name displayed in logs and API responses
- **Example**: `VMLedger Production`

### APP_VERSION

- **Type**: String
- **Required**: No
- **Default**: `1.0.0`
- **Description**: Application version number (semantic versioning)
- **Example**: `1.2.3`

### DEBUG

- **Type**: Boolean
- **Required**: No
- **Default**: `False`
- **Description**: Enable debug mode. When enabled, shows detailed error messages and enables API documentation endpoints.
- **Security**: MUST be `False` in production
- **Example**: `False`

### LOG_LEVEL

- **Type**: String (enum)
- **Required**: No
- **Default**: `INFO`
- **Description**: Logging verbosity level
- **Valid Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Example**: `INFO`
- **Validates**: Requirements 14.1-14.6

---

## API Settings

### API_HOST

- **Type**: String (IP address)
- **Required**: No
- **Default**: `0.0.0.0`
- **Description**: Host address for the API server to bind to. Use `0.0.0.0` to listen on all interfaces.
- **Example**: `0.0.0.0`

### API_PORT

- **Type**: Integer
- **Required**: No
- **Default**: `8000`
- **Description**: Port number for the API server
- **Valid Range**: 1-65535
- **Example**: `8000`

### API_WORKERS

- **Type**: Integer
- **Required**: No
- **Default**: `4`
- **Description**: Number of Gunicorn worker processes for the API server
- **Recommendation**: Set to `(2 * CPU_CORES) + 1` for optimal performance
- **Example**: `4`
- **Validates**: Requirements 13.1-13.3

---

## Database Configuration

### DATABASE_URL

See [Required Variables](#database_url) section above.

### DATABASE_POOL_SIZE

- **Type**: Integer
- **Required**: No
- **Default**: `5` (development), `10` (production)
- **Description**: Minimum number of database connections to maintain in the pool
- **Recommendation**: Increase for high-traffic deployments
- **Example**: `10`
- **Validates**: Requirements 13.4

### DATABASE_MAX_OVERFLOW

- **Type**: Integer
- **Required**: No
- **Default**: `20` (development), `30` (production)
- **Description**: Maximum number of connections that can be created beyond pool_size
- **Recommendation**: Set to 2-3x the pool size
- **Example**: `30`
- **Validates**: Requirements 13.4

---

## Redis Configuration

### REDIS_URL

- **Type**: String (Redis connection URL)
- **Required**: No
- **Default**: `redis://localhost:6379/0`
- **Description**: Redis connection string for Celery message broker and caching
- **Format**: `redis://[host]:[port]/[db]` or `redis://:[password]@[host]:[port]/[db]`
- **Example**: `redis://:SecureRedisPass@redis.example.com:6379/0`

### REDIS_PASSWORD

- **Type**: String
- **Required**: No (but recommended for production)
- **Default**: Empty string
- **Description**: Redis authentication password
- **Security**: Set this in production environments
- **Example**: `SecureRedisPassword123!`

---

## Security Settings

### SECRET_KEY

See [Required Variables](#secret_key) section above.

### ENCRYPTION_MASTER_KEY

See [Required Variables](#encryption_master_key) section above.

### JWT_ALGORITHM

- **Type**: String (enum)
- **Required**: No
- **Default**: `HS256`
- **Description**: Algorithm used for JWT token signing
- **Valid Values**: `HS256`, `HS384`, `HS512`
- **Recommendation**: Use `HS256` for best compatibility
- **Example**: `HS256`
- **Validates**: Requirements 10.3

### JWT_EXPIRATION_HOURS

- **Type**: Integer
- **Required**: No
- **Default**: `24`
- **Description**: Number of hours before JWT tokens expire
- **Valid Range**: 1-168 (1 hour to 7 days)
- **Example**: `24`
- **Validates**: Requirements 10.4

---

## Authentication Settings

### PASSWORD_MIN_LENGTH

- **Type**: Integer
- **Required**: No
- **Default**: `12`
- **Description**: Minimum password length for user registration
- **Valid Range**: 8-128
- **Example**: `12`
- **Validates**: Requirements 10.5

### MAX_LOGIN_ATTEMPTS

- **Type**: Integer
- **Required**: No
- **Default**: `5`
- **Description**: Maximum failed login attempts before account lockout
- **Valid Range**: 3-10
- **Example**: `5`
- **Validates**: Requirements 10.6

### ACCOUNT_LOCKOUT_MINUTES

- **Type**: Integer
- **Required**: No
- **Default**: `30`
- **Description**: Duration in minutes for account lockout after exceeding max login attempts
- **Valid Range**: 5-1440 (5 minutes to 24 hours)
- **Example**: `30`
- **Validates**: Requirements 10.6

### RATE_LIMIT_PER_MINUTE

- **Type**: Integer
- **Required**: No
- **Default**: `100`
- **Description**: Maximum API requests allowed per user per minute
- **Valid Range**: 10-1000
- **Example**: `100`
- **Validates**: Requirements 13.1-13.3

---

## Monitoring Settings

These settings control the monitoring intervals and behavior. Changes to these values are applied dynamically without requiring application restart.

### PING_INTERVAL_SECONDS

- **Type**: Integer
- **Required**: No
- **Default**: `60`
- **Description**: Interval in seconds between Custom_Ping health checks for each VM
- **Valid Range**: 10-3600 (10 seconds to 1 hour)
- **Recommendation**: Lower values provide faster detection but increase system load
- **Example**: `60`
- **Validates**: Requirements 4.1, 15.1

### METRICS_INTERVAL_SECONDS

- **Type**: Integer
- **Required**: No
- **Default**: `300`
- **Description**: Interval in seconds between SSH metric collection for each VM
- **Valid Range**: 60-3600 (1 minute to 1 hour)
- **Recommendation**: Lower values provide more granular data but increase SSH connections
- **Example**: `300`
- **Validates**: Requirements 5.6, 15.2

### ALERT_COOLDOWN_MINUTES

- **Type**: Integer
- **Required**: No
- **Default**: `15`
- **Description**: Cooldown period in minutes to prevent duplicate alerts for the same VM
- **Valid Range**: 1-1440 (1 minute to 24 hours)
- **Example**: `15`
- **Validates**: Requirements 8.5, 15.3

### CONCURRENT_WORKERS

- **Type**: Integer
- **Required**: No
- **Default**: `10`
- **Description**: Number of concurrent Celery worker processes for monitoring tasks
- **Valid Range**: 1-100
- **Recommendation**: Set based on number of VMs and available system resources
- **Example**: `10`
- **Validates**: Requirements 9.1-9.5, 15.4

---

## SSH Settings

### SSH_CONNECTION_TIMEOUT

- **Type**: Integer
- **Required**: No
- **Default**: `10`
- **Description**: Timeout in seconds for establishing SSH connections to VMs
- **Valid Range**: 5-60
- **Example**: `10`
- **Validates**: Requirements 5.1-5.5

### SSH_COMMAND_TIMEOUT

- **Type**: Integer
- **Required**: No
- **Default**: `30`
- **Description**: Timeout in seconds for executing SSH commands on VMs
- **Valid Range**: 10-120
- **Example**: `30`
- **Validates**: Requirements 5.1-5.5

### SSH_MAX_RETRIES

- **Type**: Integer
- **Required**: No
- **Default**: `3`
- **Description**: Maximum number of retry attempts for failed SSH connections
- **Valid Range**: 1-10
- **Example**: `3`
- **Validates**: Requirements 5.5

### SSH_RETRY_DELAY

- **Type**: Integer
- **Required**: No
- **Default**: `5`
- **Description**: Delay in seconds between SSH retry attempts
- **Valid Range**: 1-60
- **Example**: `5`
- **Validates**: Requirements 5.5

---

## Data Retention

### PING_RESULTS_RETENTION

- **Type**: Integer
- **Required**: No
- **Default**: `100`
- **Description**: Number of ping results to retain per VM (most recent records kept)
- **Valid Range**: 10-10000
- **Example**: `100`
- **Validates**: Requirements 4.6

### METRICS_RETENTION

- **Type**: Integer
- **Required**: No
- **Default**: `1000`
- **Description**: Number of metric records to retain per VM (most recent records kept)
- **Valid Range**: 100-100000
- **Example**: `1000`
- **Validates**: Requirements 5.7

### ALERTS_RETENTION_DAYS

- **Type**: Integer
- **Required**: No
- **Default**: `90`
- **Description**: Number of days to retain alert history
- **Valid Range**: 7-365
- **Example**: `90`
- **Validates**: Requirements 8.1-8.7

---

## Logging

### LOG_FILE_PATH

- **Type**: String (file path)
- **Required**: No
- **Default**: `logs/vmledger.log`
- **Description**: Path to the application log file
- **Example**: `logs/vmledger.log`
- **Validates**: Requirements 14.1-14.6

### LOG_MAX_SIZE_MB

- **Type**: Integer
- **Required**: No
- **Default**: `100`
- **Description**: Maximum log file size in megabytes before rotation
- **Valid Range**: 10-1000
- **Example**: `100`
- **Validates**: Requirements 14.5

### LOG_RETENTION_DAYS

- **Type**: Integer
- **Required**: No
- **Default**: `30`
- **Description**: Number of days to retain rotated log files
- **Valid Range**: 7-365
- **Example**: `30`
- **Validates**: Requirements 14.6

### LOG_FORMAT

- **Type**: String (enum)
- **Required**: No
- **Default**: `json`
- **Description**: Log output format
- **Valid Values**: `json`, `text`
- **Recommendation**: Use `json` for production (easier to parse), `text` for development
- **Example**: `json`
- **Validates**: Requirements 14.1-14.6

---

## Email Settings

These settings are optional and only required if email-based alerts are configured.

### SMTP_HOST

- **Type**: String (hostname)
- **Required**: No (required if using email alerts)
- **Default**: Empty string
- **Description**: SMTP server hostname for sending email alerts
- **Example**: `smtp.gmail.com`
- **Validates**: Requirements 8.3

### SMTP_PORT

- **Type**: Integer
- **Required**: No
- **Default**: `587`
- **Description**: SMTP server port
- **Valid Values**: `25` (unencrypted), `587` (TLS), `465` (SSL)
- **Recommendation**: Use `587` with TLS
- **Example**: `587`
- **Validates**: Requirements 8.3

### SMTP_USERNAME

- **Type**: String
- **Required**: No (required if using email alerts)
- **Default**: Empty string
- **Description**: SMTP authentication username
- **Example**: `alerts@example.com`
- **Validates**: Requirements 8.3

### SMTP_PASSWORD

- **Type**: String
- **Required**: No (required if using email alerts)
- **Default**: Empty string
- **Description**: SMTP authentication password
- **Security**: Sensitive credential - do not commit to version control
- **Example**: `SecureEmailPassword123!`
- **Validates**: Requirements 8.3

### SMTP_FROM_EMAIL

- **Type**: String (email address)
- **Required**: No
- **Default**: `noreply@vmledger.local`
- **Description**: Email address used as the sender for alert emails
- **Example**: `noreply@vmledger.example.com`
- **Validates**: Requirements 8.3

### SMTP_USE_TLS

- **Type**: Boolean
- **Required**: No
- **Default**: `True`
- **Description**: Enable TLS encryption for SMTP connections
- **Recommendation**: Always use `True` for security
- **Example**: `True`
- **Validates**: Requirements 8.3

---

## CORS Settings

### CORS_ORIGINS

- **Type**: String (comma-separated URLs)
- **Required**: No
- **Default**: `http://localhost:3000,http://localhost:8000`
- **Description**: Comma-separated list of allowed CORS origins for frontend access
- **Format**: `http://domain1.com,https://domain2.com`
- **Security**: Restrict to only trusted frontend domains in production
- **Example**: `https://vmledger.example.com,https://www.vmledger.example.com`

### CORS_ALLOW_CREDENTIALS

- **Type**: Boolean
- **Required**: No
- **Default**: `True`
- **Description**: Allow credentials (cookies, authorization headers) in CORS requests
- **Recommendation**: Set to `True` for JWT authentication
- **Example**: `True`

---

## Environment-Specific Configuration

### Development Environment

For local development, copy `.env.example` to `.env` and customize as needed:

```bash
cp .env.example .env
```

Key settings for development:
- `DEBUG=True` - Enable debug mode
- `LOG_LEVEL=DEBUG` - Verbose logging
- `LOG_FORMAT=text` - Human-readable logs
- `SECRET_KEY` and `ENCRYPTION_MASTER_KEY` - Can use example values (NOT for production)

### Production Environment

For production deployment, copy `.env.production.example` to `.env.production` and configure:

```bash
cp .env.production.example .env.production
```

**CRITICAL production settings:**
1. Generate secure `SECRET_KEY` and `ENCRYPTION_MASTER_KEY`
2. Set `DEBUG=False`
3. Configure production database with strong password
4. Set Redis password
5. Configure SMTP for email alerts
6. Set `CORS_ORIGINS` to your actual frontend domain(s)
7. Adjust `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` based on load
8. Set `API_WORKERS` based on CPU cores

### Docker Environment

When using Docker Compose, environment variables can be set in:
- `docker-compose.yml` (development)
- `docker-compose.prod.yml` (production)
- External `.env` file (loaded by Docker Compose)

---

## Validation

The application performs startup validation for required environment variables. If validation fails, the application will not start and will log detailed error messages.

### Validation Checks

1. **SECRET_KEY**: Must be set and not equal to default placeholder value
2. **ENCRYPTION_MASTER_KEY**: Must be set and not equal to default placeholder value
3. **DATABASE_URL**: Must be set and not contain default password
4. **LOG_LEVEL**: Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
5. **JWT_ALGORITHM**: Must be one of: HS256, HS384, HS512
6. **LOG_FORMAT**: Must be one of: json, text

### Validation Errors

If validation fails, you'll see an error like:

```
Configuration validation failed:
  - SECRET_KEY must be set to a secure random value
  - ENCRYPTION_MASTER_KEY must be set to a secure random value
  - DATABASE_URL must be properly configured with secure credentials
```

Fix the issues and restart the application.

---

## Security Best Practices

1. **Never commit sensitive values** to version control
2. **Use strong random values** for SECRET_KEY and ENCRYPTION_MASTER_KEY
3. **Rotate credentials regularly** (every 90 days recommended)
4. **Use environment-specific files** (.env for dev, .env.production for prod)
5. **Restrict file permissions** on .env files: `chmod 600 .env`
6. **Use secrets management** in production (AWS Secrets Manager, HashiCorp Vault, etc.)
7. **Enable TLS/SSL** for all external connections (database, Redis, SMTP)
8. **Set DEBUG=False** in production
9. **Use strong database passwords** (minimum 16 characters, mixed case, numbers, symbols)
10. **Backup ENCRYPTION_MASTER_KEY** securely - loss means credential data is unrecoverable

---

## Troubleshooting

### Application won't start

1. Check that all required variables are set
2. Verify SECRET_KEY and ENCRYPTION_MASTER_KEY are not default values
3. Test database connection: `psql $DATABASE_URL`
4. Test Redis connection: `redis-cli -u $REDIS_URL ping`

### Configuration not taking effect

1. Restart the application after changing .env file
2. For Docker, rebuild containers: `docker-compose up --build`
3. Check logs for configuration validation messages
4. Verify environment variables are loaded: Check startup logs

### Monitoring intervals not changing

1. Monitoring intervals (PING_INTERVAL_SECONDS, METRICS_INTERVAL_SECONDS) are read dynamically by Celery Beat
2. Changes take effect on the next scheduled run (no restart required)
3. Check Celery Beat logs to verify new intervals are being used

---

## Reference

- **Requirements Document**: `.kiro/specs/vmledger-app/requirements.md`
- **Design Document**: `.kiro/specs/vmledger-app/design.md`
- **Configuration Module**: `vmledger/config.py`
- **Example Files**: `.env.example`, `.env.production.example`

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Maintained By**: VMLedger Development Team
