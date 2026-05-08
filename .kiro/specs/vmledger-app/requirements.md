# Requirements Document

## Introduction

VMLedger is a lightweight Configuration Management Database (CMDB) and monitoring tool designed for personal VM infrastructure management. The system enables users to register virtual machines, track deployment metadata, monitor health status in real-time, and receive alerts when issues occur. The system uses an agentless architecture, collecting metrics via SSH without requiring agent installation on target VMs.

## Glossary

- **VMLedger_System**: The complete web application including frontend, backend API, database, and background workers
- **VM_Registry**: The database component storing VM registration data and metadata
- **User**: An authenticated person who registers and manages their own VMs
- **VM**: A virtual machine registered in the system with associated metadata
- **Custom_Ping**: A health check combining ICMP ping and TCP port connectivity test
- **Metric_Collector**: The SSH-based component that retrieves resource usage data from VMs
- **Background_Worker**: Celery worker process that executes monitoring tasks asynchronously
- **Credential_Store**: The encrypted storage mechanism for SSH keys and sensitive authentication data
- **Deployment_Notes**: Markdown-formatted documentation describing software and configurations on a VM
- **Alert_Handler**: The component responsible for sending notifications when VMs become unreachable
- **Search_Engine**: The full-text search component for finding VMs by various criteria

## Requirements

### Requirement 1: VM Registration

**User Story:** As a user, I want to register my VMs with complete metadata, so that I can track and manage my infrastructure inventory.

#### Acceptance Criteria

1. THE VM_Registry SHALL accept VM registrations with IP address, hostname, domain, SSH port, and tags
2. WHEN a user submits a VM registration, THE VMLedger_System SHALL validate that the IP address is in valid IPv4 or IPv6 format
3. WHEN a user submits a VM registration, THE VMLedger_System SHALL validate that the SSH port is between 1 and 65535
4. THE VMLedger_System SHALL allow users to assign multiple tags to a single VM
5. WHEN a VM is registered, THE VMLedger_System SHALL associate it with the authenticated user's account
6. THE VMLedger_System SHALL prevent duplicate VM registrations for the same IP address and SSH port combination by the same user

### Requirement 2: Credential Security

**User Story:** As a user, I want my SSH credentials stored securely, so that my VM access remains protected.

#### Acceptance Criteria

1. THE Credential_Store SHALL encrypt all SSH private keys using AES-256 encryption before storage
2. THE Credential_Store SHALL encrypt all password-based credentials using AES-256 encryption before storage
3. WHEN storing credentials, THE VMLedger_System SHALL use unique encryption keys per user
4. THE VMLedger_System SHALL prioritize SSH key-based authentication over password-based authentication
5. WHEN a user provides an SSH private key, THE VMLedger_System SHALL validate the key format before storage
6. THE VMLedger_System SHALL prevent credential data from appearing in application logs or error messages

### Requirement 3: User Isolation and Access Control

**User Story:** As a user, I want to see only my own VMs, so that my infrastructure data remains private.

#### Acceptance Criteria

1. WHEN a user requests VM data, THE VMLedger_System SHALL return only VMs associated with that user's account
2. WHEN a user attempts to modify a VM, THE VMLedger_System SHALL verify the VM belongs to that user before allowing changes
3. WHEN a user attempts to delete a VM, THE VMLedger_System SHALL verify the VM belongs to that user before allowing deletion
4. THE VMLedger_System SHALL prevent users from accessing monitoring data for VMs they do not own
5. THE VMLedger_System SHALL prevent users from accessing deployment notes for VMs they do not own

### Requirement 4: Health Check Monitoring

**User Story:** As a user, I want the system to periodically check if my VMs are reachable, so that I can detect connectivity issues.

#### Acceptance Criteria

1. THE Background_Worker SHALL execute Custom_Ping checks for all registered VMs at configurable intervals
2. WHEN performing a Custom_Ping, THE VMLedger_System SHALL execute an ICMP ping to the VM's IP address
3. WHEN performing a Custom_Ping, THE VMLedger_System SHALL attempt a TCP connection to the VM's SSH port
4. WHEN a Custom_Ping succeeds, THE VMLedger_System SHALL record the timestamp and response time in the VM_Registry
5. WHEN a Custom_Ping fails, THE VMLedger_System SHALL record the failure timestamp and error type in the VM_Registry
6. THE VMLedger_System SHALL maintain a history of the last 100 Custom_Ping results per VM

### Requirement 5: Resource Metrics Collection

**User Story:** As a user, I want to see CPU, RAM, and disk usage for my VMs, so that I can monitor resource consumption.

#### Acceptance Criteria

1. THE Metric_Collector SHALL retrieve CPU usage percentage via SSH commands without requiring agent installation
2. THE Metric_Collector SHALL retrieve RAM usage (used and total) via SSH commands without requiring agent installation
3. THE Metric_Collector SHALL retrieve disk usage (used, total, and percentage) via SSH commands without requiring agent installation
4. WHEN collecting metrics, THE Metric_Collector SHALL use the stored SSH credentials for authentication
5. WHEN an SSH connection fails, THE Metric_Collector SHALL log the error and mark the VM as unreachable
6. THE Background_Worker SHALL collect resource metrics for all registered VMs at configurable intervals
7. THE VMLedger_System SHALL store the most recent 1000 metric data points per VM for historical analysis

### Requirement 6: Deployment Documentation

**User Story:** As a user, I want to document installed software and configurations per VM, so that I can track what is deployed where.

#### Acceptance Criteria

1. THE VMLedger_System SHALL provide a Deployment_Notes field for each VM that accepts Markdown-formatted text
2. WHEN a user saves Deployment_Notes, THE VMLedger_System SHALL preserve Markdown formatting
3. WHEN displaying Deployment_Notes, THE VMLedger_System SHALL render Markdown as formatted HTML
4. THE VMLedger_System SHALL allow Deployment_Notes up to 50000 characters in length
5. WHEN a user updates Deployment_Notes, THE VMLedger_System SHALL save the changes immediately

### Requirement 7: Global Search

**User Story:** As a user, I want to search across all my VMs by IP, hostname, or deployment notes, so that I can quickly find specific infrastructure.

#### Acceptance Criteria

1. THE Search_Engine SHALL index VM IP addresses, hostnames, domains, tags, and Deployment_Notes for full-text search
2. WHEN a user enters a search query, THE Search_Engine SHALL return all matching VMs owned by that user within 500 milliseconds
3. THE Search_Engine SHALL support partial word matching (e.g., "ngin" matches "Nginx")
4. THE Search_Engine SHALL rank search results by relevance with exact matches appearing first
5. WHEN searching Deployment_Notes, THE Search_Engine SHALL highlight matching text in the results
6. THE Search_Engine SHALL return results containing any of the search terms (OR logic)

### Requirement 8: Alerting and Notifications

**User Story:** As a user, I want to receive notifications when my VMs become unreachable, so that I can respond to outages quickly.

#### Acceptance Criteria

1. WHEN a VM fails a Custom_Ping check, THE Alert_Handler SHALL trigger a notification
2. THE Alert_Handler SHALL support webhook-based notifications with configurable URLs
3. THE Alert_Handler SHALL support email-based notifications with configurable recipient addresses
4. WHEN sending an alert, THE Alert_Handler SHALL include the VM hostname, IP address, and failure timestamp
5. THE VMLedger_System SHALL prevent duplicate alerts for the same VM within a 15-minute window
6. WHEN a previously unreachable VM becomes reachable, THE Alert_Handler SHALL send a recovery notification
7. WHERE a user has configured alert preferences, THE Alert_Handler SHALL respect those preferences per VM

### Requirement 9: Concurrent Monitoring Scalability

**User Story:** As a system administrator, I want the monitoring system to handle 50+ VMs concurrently, so that the system scales with infrastructure growth.

#### Acceptance Criteria

1. THE Background_Worker SHALL process Custom_Ping checks for at least 50 VMs concurrently
2. THE Background_Worker SHALL process metric collection for at least 50 VMs concurrently
3. WHEN monitoring 50 VMs, THE VMLedger_System SHALL complete a full monitoring cycle within 5 minutes
4. THE VMLedger_System SHALL distribute monitoring tasks across multiple Background_Worker processes
5. WHEN a Background_Worker fails, THE VMLedger_System SHALL reassign pending tasks to available workers

### Requirement 10: User Authentication

**User Story:** As a user, I want to authenticate securely, so that only I can access my VM data.

#### Acceptance Criteria

1. THE VMLedger_System SHALL require authentication before allowing access to any VM data
2. THE VMLedger_System SHALL support password-based user authentication with bcrypt hashing
3. WHEN a user logs in, THE VMLedger_System SHALL create a session token valid for 24 hours
4. WHEN a session token expires, THE VMLedger_System SHALL require re-authentication
5. THE VMLedger_System SHALL enforce password complexity requirements (minimum 12 characters, mixed case, numbers, special characters)
6. WHEN a user fails authentication 5 times within 15 minutes, THE VMLedger_System SHALL temporarily lock the account for 30 minutes

### Requirement 11: VM Modification and Deletion

**User Story:** As a user, I want to update or remove VM registrations, so that I can keep my inventory accurate.

#### Acceptance Criteria

1. WHEN a user requests to update a VM, THE VMLedger_System SHALL allow modification of IP address, hostname, domain, SSH port, tags, and credentials
2. WHEN a user updates VM credentials, THE VMLedger_System SHALL re-encrypt the new credentials before storage
3. WHEN a user deletes a VM, THE VMLedger_System SHALL remove all associated monitoring data and deployment notes
4. WHEN a user deletes a VM, THE VMLedger_System SHALL remove all associated credentials from the Credential_Store
5. THE VMLedger_System SHALL require explicit confirmation before deleting a VM

### Requirement 12: Dashboard Visualization

**User Story:** As a user, I want a visual dashboard showing VM status at a glance, so that I can quickly assess infrastructure health.

#### Acceptance Criteria

1. THE VMLedger_System SHALL display all registered VMs in a dashboard view with status indicators
2. WHEN a VM is reachable, THE VMLedger_System SHALL display a green status indicator
3. WHEN a VM is unreachable, THE VMLedger_System SHALL display a red status indicator
4. THE VMLedger_System SHALL display the most recent CPU, RAM, and disk usage metrics for each VM
5. THE VMLedger_System SHALL display the last successful ping timestamp for each VM
6. THE VMLedger_System SHALL refresh dashboard data automatically every 30 seconds without requiring page reload

### Requirement 13: API Performance

**User Story:** As a user, I want fast API responses, so that the dashboard remains responsive.

#### Acceptance Criteria

1. WHEN a user requests the VM list, THE VMLedger_System SHALL respond within 200 milliseconds for up to 100 VMs
2. WHEN a user requests VM details, THE VMLedger_System SHALL respond within 100 milliseconds
3. WHEN a user submits a VM registration, THE VMLedger_System SHALL respond within 500 milliseconds
4. THE VMLedger_System SHALL use database connection pooling to optimize query performance
5. THE VMLedger_System SHALL use database indexes on frequently queried fields (user_id, IP address, hostname)

### Requirement 14: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive error logging, so that I can troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN an SSH connection fails, THE VMLedger_System SHALL log the VM identifier, error type, and timestamp
2. WHEN a monitoring task fails, THE Background_Worker SHALL log the failure details and continue processing other tasks
3. WHEN a database operation fails, THE VMLedger_System SHALL log the error and return a user-friendly error message
4. THE VMLedger_System SHALL log all authentication attempts with timestamps and outcomes
5. THE VMLedger_System SHALL rotate log files when they exceed 100 MB in size
6. THE VMLedger_System SHALL retain log files for at least 30 days

### Requirement 15: Configuration Management

**User Story:** As a system administrator, I want configurable monitoring intervals and thresholds, so that I can tune the system for my needs.

#### Acceptance Criteria

1. THE VMLedger_System SHALL allow configuration of Custom_Ping check intervals (default 60 seconds)
2. THE VMLedger_System SHALL allow configuration of metric collection intervals (default 300 seconds)
3. THE VMLedger_System SHALL allow configuration of alert notification cooldown periods (default 15 minutes)
4. THE VMLedger_System SHALL allow configuration of concurrent worker limits (default 10)
5. THE VMLedger_System SHALL load configuration from environment variables or a configuration file
6. WHEN configuration changes are made, THE VMLedger_System SHALL apply them without requiring application restart for interval-based settings

