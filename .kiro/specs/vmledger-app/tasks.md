# Implementation Plan: VMLedger

## Overview

This implementation plan breaks down the VMLedger system into discrete, actionable coding tasks. The system is a lightweight CMDB and monitoring tool with an agentless architecture using FastAPI (backend), Next.js (frontend), PostgreSQL (database), and Celery (background workers).

The implementation follows a bottom-up approach: database schema → core services → API layer → background workers → frontend → testing → deployment configuration.

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - Create Python project structure with FastAPI application
  - Set up virtual environment and install core dependencies (FastAPI, SQLAlchemy, Pydantic, Celery, Redis, Paramiko)
  - Configure environment variables and settings management
  - Set up logging configuration with structured JSON logging
  - Create database connection pooling configuration
  - _Requirements: 13.4, 14.1-14.6_

- [x] 2. Implement database schema and migrations
  - [x] 2.1 Create SQLAlchemy models for all tables
    - Implement Users table with password hashing and encryption salt
    - Implement VMs table with full-text search vector column
    - Implement Credentials table with encrypted credential storage
    - Implement PingResults table with indexing strategy
    - Implement Metrics table with indexing strategy
    - Implement Alerts table
    - Implement AlertConfigs table
    - Add all foreign key relationships and constraints
    - _Requirements: 1.1-1.6, 2.1-2.6, 3.1-3.5, 4.1-4.6, 5.1-5.7, 6.1-6.5, 8.1-8.7_
  
  - [x]* 2.2 Write property test for IP address validation
    - **Property 1: IP Address Validation**
    - **Validates: Requirements 1.2**
  
  - [x]* 2.3 Write property test for SSH port validation
    - **Property 2: SSH Port Range Validation**
    - **Validates: Requirements 1.3**
  
  - [x] 2.4 Create Alembic migration scripts
    - Initialize Alembic configuration
    - Create initial migration for all tables
    - Add GIN indexes for full-text search and array fields
    - Add trigger for tsvector auto-update on VMs table
    - _Requirements: 7.1, 13.5_

- [x] 3. Implement credential encryption and management
  - [x] 3.1 Create CredentialManager service
    - Implement AES-256-GCM encryption using Fernet
    - Implement PBKDF2-HMAC-SHA256 key derivation with user-specific salts
    - Implement encrypt_ssh_key and decrypt_ssh_key methods
    - Implement encrypt_password and decrypt_password methods
    - Implement SSH key format validation using Paramiko
    - Implement delete_credentials method
    - _Requirements: 2.1-2.6, 11.2, 11.4_
  
  - [ ]* 3.2 Write property test for SSH key format validation
    - **Property 3: SSH Key Format Validation**
    - **Validates: Requirements 2.5**
  
  - [ ]* 3.3 Write property test for credential encryption round-trip
    - **Property 4: Credential Encryption Round-Trip**
    - **Validates: Requirements 2.1, 2.2, 11.2**
  
  - [ ]* 3.4 Write unit tests for CredentialManager
    - Test encryption with different key types (RSA, ECDSA, Ed25519)
    - Test decryption failure scenarios
    - Test key validation edge cases
    - _Requirements: 2.1-2.6_

- [x] 4. Implement authentication and user management
  - [x] 4.1 Create AuthService with bcrypt password hashing
    - Implement register_user with password complexity validation
    - Implement authenticate with bcrypt verification
    - Implement JWT token generation with HS256 signing
    - Implement validate_token with expiry checking
    - Implement refresh_token functionality
    - Implement logout with token invalidation
    - Implement rate limiting using Redis counters
    - Implement account lockout after 5 failed attempts
    - _Requirements: 10.1-10.6_
  
  - [ ]* 4.2 Write property test for password complexity validation
    - **Property 16: Password Complexity Validation**
    - **Validates: Requirements 10.5**
  
  - [ ]* 4.3 Write property test for token expiry enforcement
    - **Property 15: Token Expiry Enforcement**
    - **Validates: Requirements 10.4**
  
  - [ ]* 4.4 Write property test for authentication attempt logging
    - **Property 17: Authentication Attempt Logging**
    - **Validates: Requirements 14.4**
  
  - [ ]* 4.5 Write unit tests for AuthService
    - Test successful registration and login
    - Test failed login attempts and lockout
    - Test token expiry and refresh
    - Test rate limiting behavior
    - _Requirements: 10.1-10.6_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement VM registry service with user isolation
  - [x] 6.1 Create VMRegistryService with CRUD operations
    - Implement create_vm with input validation using Pydantic
    - Implement get_vm with user ownership verification
    - Implement list_vms with user filtering
    - Implement update_vm with user ownership verification
    - Implement delete_vm with cascade deletion of credentials and monitoring data
    - Implement check_duplicate to prevent duplicate IP+port per user
    - Add user isolation enforcement on all operations
    - _Requirements: 1.1-1.6, 3.1-3.5, 11.1-11.5_
  
  - [ ]* 6.2 Write property test for user isolation enforcement
    - **Property 5: User Isolation Enforcement**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
  
  - [ ]* 6.3 Write property test for Markdown preservation
    - **Property 7: Markdown Preservation**
    - **Validates: Requirements 6.2**
  
  - [ ]* 6.4 Write unit tests for VMRegistryService
    - Test duplicate VM rejection
    - Test deployment notes at max length (50,000 chars)
    - Test tag limit enforcement (20 tags max)
    - Test cascade deletion behavior
    - _Requirements: 1.1-1.6, 6.1-6.5, 11.1-11.5_

- [x] 7. Implement health check service (Custom_Ping)
  - [x] 7.1 Create HealthCheckService
    - Implement check_icmp_ping using ping3 library
    - Implement check_tcp_port using socket with 5-second timeout
    - Implement execute_ping combining ICMP and TCP checks
    - Implement store_ping_result to save results to database
    - Implement get_ping_history with limit parameter
    - Add error type classification (ICMP_TIMEOUT, TCP_REFUSED, HOST_UNREACHABLE, TIMEOUT)
    - _Requirements: 4.1-4.6_
  
  - [ ]* 7.2 Write unit tests for HealthCheckService
    - Test successful ping with both ICMP and TCP success
    - Test partial failure scenarios (ICMP success, TCP fail)
    - Test complete failure scenarios
    - Test response time measurement
    - Mock socket and ping3 for deterministic tests
    - _Requirements: 4.1-4.6_

- [x] 8. Implement SSH metric collector service
  - [x] 8.1 Create MetricCollectorService with OS detection
    - Implement get_cpu_usage with Linux and macOS command variants
    - Implement get_memory_usage with Linux and macOS command variants
    - Implement get_disk_usage with df command parsing
    - Implement collect_metrics orchestrating all metric collection
    - Implement store_metrics to save results to database
    - Implement get_metric_history with limit parameter
    - Add SSH connection management with 10-second timeout
    - Add command execution timeout (30 seconds)
    - Add retry logic (3 attempts with 5-second delay)
    - Implement OS detection using uname command
    - _Requirements: 5.1-5.7_
  
  - [ ]* 8.2 Write integration tests for MetricCollectorService
    - Test metric collection with mock SSH server
    - Test connection timeout handling
    - Test authentication failure handling
    - Test command execution timeout
    - Test OS detection and command selection
    - _Requirements: 5.1-5.7_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement full-text search engine
  - [x] 10.1 Create SearchEngineService using PostgreSQL full-text search
    - Implement search_vms with ts_query construction
    - Implement index_vm to update search_vector on insert
    - Implement update_index to update search_vector on update
    - Implement delete_from_index to handle deletions
    - Implement highlight_matches using ts_headline
    - Add ranking using ts_rank for relevance sorting
    - Implement OR logic for multi-term queries
    - _Requirements: 7.1-7.6_
  
  - [ ]* 10.2 Write property test for partial search matching
    - **Property 8: Partial Search Matching**
    - **Validates: Requirements 7.3**
  
  - [ ]* 10.3 Write property test for search result ranking
    - **Property 9: Search Result Ranking**
    - **Validates: Requirements 7.4**
  
  - [ ]* 10.4 Write property test for search highlighting
    - **Property 10: Search Highlighting**
    - **Validates: Requirements 7.5**
  
  - [ ]* 10.5 Write property test for search boolean OR logic
    - **Property 11: Search Boolean OR Logic**
    - **Validates: Requirements 7.6**
  
  - [ ]* 10.6 Write unit tests for SearchEngineService
    - Test search performance (< 500ms for 100 VMs)
    - Test search across all indexed fields
    - Test highlighting in deployment notes
    - Test ranking with exact vs partial matches
    - _Requirements: 7.1-7.6_

- [x] 11. Implement alert handler service
  - [x] 11.1 Create AlertHandlerService
    - Implement check_alert_conditions to determine when to alert
    - Implement send_webhook with retry logic (3 attempts, exponential backoff)
    - Implement send_email using SMTP
    - Implement check_cooldown using 15-minute window
    - Implement record_alert_sent to track alert history
    - Implement send_alert orchestrating webhook and email dispatch
    - Add webhook payload formatting with VM details
    - Add email template formatting
    - _Requirements: 8.1-8.7_
  
  - [ ]* 11.2 Write property test for alert payload completeness
    - **Property 12: Alert Payload Completeness**
    - **Validates: Requirements 8.4**
  
  - [ ]* 11.3 Write property test for alert cooldown prevention
    - **Property 13: Alert Cooldown Prevention**
    - **Validates: Requirements 8.5**
  
  - [ ]* 11.4 Write unit tests for AlertHandlerService
    - Test webhook retry logic
    - Test email sending with SMTP mock
    - Test cooldown enforcement
    - Test recovery notification triggering
    - Test alert preference respect per VM
    - _Requirements: 8.1-8.7_

- [x] 12. Implement data retention policies
  - [x] 12.1 Create data cleanup service
    - Implement cleanup_ping_results using window functions (keep last 100 per VM)
    - Implement cleanup_metrics using window functions (keep last 1000 per VM)
    - Implement cleanup_alerts (retain for 90 days)
    - _Requirements: 4.6, 5.7_
  
  - [ ]* 12.2 Write property test for data retention policy
    - **Property 6: Data Retention Policy**
    - **Validates: Requirements 4.6, 5.7**
  
  - [ ]* 12.3 Write unit tests for data cleanup
    - Test ping results retention with >100 records
    - Test metrics retention with >1000 records
    - Test alert retention with old records
    - _Requirements: 4.6, 5.7_

- [x] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement Celery background workers and task scheduling
  - [x] 14.1 Set up Celery application with Redis broker
    - Configure Celery app with Redis as message broker and result backend
    - Configure worker pool (prefork with 10 processes)
    - Configure task routing and rate limiting (50 tasks/second)
    - Configure task timeouts (60s for ping, 120s for metrics)
    - Configure result expiration (1 hour)
    - _Requirements: 9.1-9.5, 15.1-15.6_
  
  - [x] 14.2 Implement Celery Beat schedule
    - Configure ping_check_task to run every 60 seconds
    - Configure collect_metrics_task to run every 300 seconds
    - Configure cleanup_old_data_task to run daily at 2 AM
    - Make intervals configurable via environment variables
    - _Requirements: 4.1, 5.6, 15.1-15.3_
  
  - [x] 14.3 Implement ping_check_task
    - Create Celery task that accepts vm_id parameter
    - Retrieve VM from database
    - Execute HealthCheckService.execute_ping
    - Store ping result
    - Trigger alert check if ping failed
    - Add retry logic (3 attempts, 60-second countdown)
    - _Requirements: 4.1-4.6, 8.1_
  
  - [x] 14.4 Implement collect_metrics_task
    - Create Celery task that accepts vm_id parameter
    - Retrieve VM and credentials from database
    - Decrypt credentials using CredentialManager
    - Execute MetricCollectorService.collect_metrics
    - Store metrics result
    - Add retry logic (3 attempts, exponential backoff)
    - _Requirements: 5.1-5.7_
  
  - [x] 14.5 Implement schedule_ping_checks orchestrator task
    - Query all active VMs from database
    - Dispatch ping_check_task for each VM
    - Implement concurrent processing (10 workers)
    - _Requirements: 9.1-9.5_
  
  - [x] 14.6 Implement schedule_metric_collection orchestrator task
    - Query all active VMs from database
    - Dispatch collect_metrics_task for each VM
    - Implement concurrent processing (10 workers)
    - _Requirements: 9.1-9.5_
  
  - [x] 14.7 Implement cleanup_historical_data task
    - Call data cleanup service for ping results
    - Call data cleanup service for metrics
    - Call data cleanup service for alerts
    - _Requirements: 4.6, 5.7_
  
  - [ ]* 14.8 Write integration tests for Celery tasks
    - Test ping_check_task execution
    - Test collect_metrics_task execution
    - Test task retry behavior
    - Test concurrent task processing
    - Test full monitoring cycle completion time (< 5 minutes for 50 VMs)
    - _Requirements: 9.1-9.5_

- [x] 15. Implement FastAPI REST API endpoints
  - [x] 15.1 Create authentication middleware
    - Implement JWT token validation middleware
    - Implement rate limiting middleware (100 requests/minute per user)
    - Add CORS configuration for frontend integration
    - _Requirements: 10.1-10.6, 13.1-13.5_
  
  - [ ]* 15.2 Write property test for unauthenticated request rejection
    - **Property 14: Unauthenticated Request Rejection**
    - **Validates: Requirements 10.1**
  
  - [x] 15.3 Implement authentication endpoints
    - POST /api/auth/register with password complexity validation
    - POST /api/auth/login with rate limiting
    - POST /api/auth/logout with token invalidation
    - POST /api/auth/refresh for token refresh
    - _Requirements: 10.1-10.6_
  
  - [x] 15.4 Implement VM management endpoints
    - GET /api/vms with pagination and user filtering
    - POST /api/vms with validation and credential encryption
    - GET /api/vms/{vm_id} with user ownership check
    - PUT /api/vms/{vm_id} with user ownership check
    - DELETE /api/vms/{vm_id} with user ownership check and cascade deletion
    - GET /api/vms/search with query parameter
    - _Requirements: 1.1-1.6, 3.1-3.5, 7.1-7.6, 11.1-11.5_
  
  - [x] 15.5 Implement monitoring data endpoints
    - GET /api/vms/{vm_id}/metrics with history limit
    - GET /api/vms/{vm_id}/ping with history limit
    - GET /api/vms/{vm_id}/status with latest data
    - _Requirements: 4.1-4.6, 5.1-5.7, 12.1-12.6_
  
  - [x] 15.6 Implement alert configuration endpoints
    - GET /api/vms/{vm_id}/alerts/config
    - PUT /api/vms/{vm_id}/alerts/config with validation
    - GET /api/vms/{vm_id}/alerts/history
    - _Requirements: 8.1-8.7_
  
  - [x] 15.7 Implement dashboard endpoint
    - GET /api/dashboard returning all VMs with latest metrics
    - Optimize query with joins to reduce database round-trips
    - Add caching with 30-second TTL using Redis
    - _Requirements: 12.1-12.6, 13.1-13.5_
  
  - [ ]* 15.8 Write unit tests for API endpoints
    - Test all endpoints with valid and invalid inputs
    - Test authentication and authorization enforcement
    - Test error response formats
    - Test pagination behavior
    - _Requirements: 1.1-15.6_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Implement Next.js frontend dashboard
  - [x] 17.1 Set up Next.js 14 project with TypeScript
    - Initialize Next.js project with App Router
    - Install dependencies (React, TailwindCSS, React Query, Axios)
    - Configure TypeScript and ESLint
    - Set up API client with authentication token handling
    - _Requirements: 12.1-12.6_
  
  - [x] 17.2 Create authentication pages
    - Implement login page with form validation
    - Implement registration page with password complexity validation
    - Implement session token storage in localStorage
    - Implement automatic token refresh
    - Add logout functionality
    - _Requirements: 10.1-10.6_
  
  - [x] 17.3 Create VM registration and edit forms
    - Implement VM registration form with all fields
    - Add IP address format validation
    - Add SSH port range validation
    - Add SSH key format validation
    - Add tags input with max 20 tags
    - Implement VM edit form with pre-populated data
    - Add confirmation dialog for VM deletion
    - _Requirements: 1.1-1.6, 11.1-11.5_
  
  - [x] 17.4 Create dashboard page with VM list
    - Implement VM list with status indicators (green/red)
    - Display latest CPU, RAM, disk metrics for each VM
    - Display last seen timestamp
    - Add auto-refresh every 30 seconds using React Query
    - Implement loading states and error handling
    - _Requirements: 12.1-12.6_
  
  - [x] 17.5 Create VM details page
    - Display complete VM metadata
    - Display metric history charts (CPU, RAM, disk over time)
    - Display ping history with response times
    - Display alert history
    - Add tabs for different data views
    - _Requirements: 4.1-4.6, 5.1-5.7, 8.1-8.7_
  
  - [x] 17.6 Create deployment notes editor
    - Implement Markdown editor with preview
    - Add character count (max 50,000)
    - Implement auto-save functionality
    - Render Markdown as formatted HTML in view mode
    - _Requirements: 6.1-6.5_
  
  - [x] 17.7 Create search interface
    - Implement search input with debounced queries (300ms)
    - Display search results with highlighting
    - Show relevance ranking
    - Add filters for tags and status
    - _Requirements: 7.1-7.6_
  
  - [x] 17.8 Create alert configuration page
    - Implement alert config form per VM
    - Add webhook URL validation
    - Add email address validation
    - Add cooldown period configuration
    - Add enable/disable toggle
    - _Requirements: 8.1-8.7_
  
  - [ ]* 17.9 Write E2E tests for frontend
    - Test user registration and login flow
    - Test VM registration to alert workflow
    - Test search functionality
    - Test dashboard auto-refresh
    - Test deployment notes editing
    - _Requirements: All user-facing requirements_

- [x] 18. Implement error handling and logging
  - [x] 18.1 Add structured error handling across all services
    - Implement validation error responses (HTTP 400)
    - Implement authentication error responses (HTTP 401/403)
    - Implement internal error responses (HTTP 500)
    - Add request ID generation for error tracking
    - _Requirements: 14.1-14.6_
  
  - [x] 18.2 Configure logging with sensitive data protection
    - Set up structured JSON logging
    - Implement log level configuration (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Add credential redaction in logs
    - Configure log rotation (100 MB max size)
    - Configure log retention (30 days)
    - _Requirements: 2.6, 14.1-14.6_
  
  - [x] 18.3 Implement retry strategies
    - Add SSH operation retry logic (3 attempts, 5s delay)
    - Add webhook retry logic (3 attempts, exponential backoff)
    - Add database operation retry logic (2 attempts, 1s delay)
    - Add Celery task retry logic (3 attempts, exponential backoff)
    - _Requirements: 5.5, 8.2, 9.5_

- [x] 19. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Create deployment configuration
  - [x] 20.1 Create Docker configuration
    - Write Dockerfile for FastAPI application
    - Write Dockerfile for Celery workers
    - Write docker-compose.yml for local development
    - Write docker-compose.prod.yml for production deployment
    - Include PostgreSQL, Redis, FastAPI, Celery Beat, Celery Workers
    - _Requirements: 15.1-15.6_
  
  - [x] 20.2 Create environment configuration
    - Create .env.example with all required variables
    - Document all environment variables
    - Add validation for required environment variables on startup
    - _Requirements: 15.1-15.6_
  
  - [x] 20.3 Create database migration scripts
    - Add Alembic upgrade/downgrade commands to deployment docs
    - Create database initialization script
    - Add database backup script
    - _Requirements: 13.4, 13.5_
  
  - [x] 20.4 Create production deployment guide
    - Document load balancer configuration (Nginx)
    - Document FastAPI deployment with Gunicorn + Uvicorn
    - Document Celery worker deployment
    - Document PostgreSQL replication setup
    - Document Redis Sentinel configuration
    - Document monitoring setup (Prometheus, Grafana)
    - Document security hardening checklist
    - _Requirements: 9.1-9.5, 13.1-13.5_

- [x] 21. Performance optimization and testing
  - [ ]* 21.1 Run performance tests with Locust
    - Test API load (100 concurrent users, 1000 req/s)
    - Test dashboard load (50 concurrent users)
    - Test monitoring scalability (100 VMs concurrently)
    - Test search performance (< 500ms for 1000 VMs)
    - _Requirements: 7.2, 9.1-9.5, 13.1-13.3_
  
  - [x] 21.2 Optimize database queries
    - Run EXPLAIN ANALYZE on slow queries
    - Add missing indexes based on query patterns
    - Optimize dashboard query with proper joins
    - Consider partitioning metrics table by month
    - _Requirements: 13.1-13.5_
  
  - [x] 21.3 Implement caching strategy
    - Add Redis caching for dashboard data (30s TTL)
    - Add Redis caching for VM list (30s TTL)
    - Implement cache invalidation on VM updates
    - _Requirements: 12.6, 13.1-13.5_

- [x] 22. Security hardening
  - [ ]* 22.1 Run security tests
    - Test SQL injection prevention
    - Test XSS prevention in deployment notes
    - Test CSRF token validation
    - Test session token tampering
    - Test user isolation boundaries
    - Test rate limiting bypass attempts
    - Audit logs for sensitive data leakage
    - _Requirements: 2.6, 3.1-3.5, 10.1-10.6_
  
  - [x] 22.2 Implement production security checklist
    - Enable HTTPS only with TLS 1.3
    - Add HSTS headers
    - Add CSP headers
    - Enable database connection encryption
    - Add Redis password authentication
    - Enable Celery message signing
    - Configure CORS properly
    - _Requirements: 2.1-2.6, 10.1-10.6_

- [x] 23. Final checkpoint - Ensure all tests pass and system is production-ready
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Property-based tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- Integration tests validate external dependencies (SSH, database, Redis)
- E2E tests validate complete user workflows
- Checkpoints ensure incremental validation and provide opportunities for user feedback
- The implementation uses Python 3.11+ with FastAPI, PostgreSQL 15+, Redis 7+, and Celery
- All credentials are encrypted with AES-256-GCM before storage
- User isolation is enforced at both database and application layers
- Background workers handle all monitoring tasks asynchronously
- The system is designed to scale to 50+ VMs with sub-5-minute monitoring cycles
