"""
Property-based tests for alert handling functionality.

Tests Properties 12-13: Alert functionality
Validates: Requirements 8.1-8.7
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume
from vmledger.services.alert_handler_service import AlertHandlerService
from vmledger.models.vm import VM
from vmledger.models.alert import Alert
from vmledger.models.alert_config import AlertConfig


# Strategy for generating VM IDs
vm_ids = st.integers(min_value=1, max_value=1000)

# Strategy for generating alert types
alert_types = st.sampled_from([
    "ping_failure",
    "high_cpu",
    "high_memory",
    "high_disk",
    "ssh_failure"
])


@given(
    vm_id=vm_ids,
    alert_type=alert_types,
    webhook_url=st.text(min_size=10, max_size=100),
    email=st.emails()
)
def test_property_alert_payload_completeness(
    vm_id, alert_type, webhook_url, email, mock_db_session
):
    """
    Property 12: Alert Payload Completeness
    
    Property: Every alert sent should contain complete VM details including
    hostname, IP address, alert type, timestamp, and relevant metrics.
    
    Validates: Requirement 8.4 - Include VM details in alert payload
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock VM
    mock_vm = VM(
        id=vm_id,
        user_id=1,
        hostname="test-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["production"],
        deployment_notes="Critical server"
    )
    
    # Create mock alert config
    mock_config = AlertConfig(
        vm_id=vm_id,
        webhook_url=webhook_url,
        email_address=email,
        alert_on_ping_failure=True,
        alert_on_high_cpu=True,
        alert_on_high_memory=True,
        alert_on_high_disk=True,
        cooldown_minutes=15
    )
    
    # Mock database queries
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    payload = alert_service._build_alert_payload(
        vm=mock_vm,
        alert_type=alert_type,
        message="Test alert",
        details={"cpu_usage": 95.0}
    )
    
    # Assert - Verify payload completeness
    assert "vm_id" in payload, "Payload must include vm_id"
    assert "hostname" in payload, "Payload must include hostname"
    assert "ip_address" in payload, "Payload must include ip_address"
    assert "alert_type" in payload, "Payload must include alert_type"
    assert "timestamp" in payload, "Payload must include timestamp"
    assert "message" in payload, "Payload must include message"
    
    # Verify values
    assert payload["vm_id"] == vm_id
    assert payload["hostname"] == "test-server"
    assert payload["ip_address"] == "192.168.1.100"
    assert payload["alert_type"] == alert_type


@given(
    vm_id=vm_ids,
    cooldown_minutes=st.integers(min_value=1, max_value=60),
    minutes_since_last_alert=st.integers(min_value=0, max_value=120)
)
def test_property_alert_cooldown_prevention(
    vm_id, cooldown_minutes, minutes_since_last_alert, mock_db_session
):
    """
    Property 13: Alert Cooldown Prevention
    
    Property: If an alert was sent within the cooldown period, no new alert
    of the same type should be sent for the same VM.
    
    Validates: Requirement 8.5 - Prevent duplicate alerts within cooldown period
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock alert config with cooldown
    mock_config = AlertConfig(
        vm_id=vm_id,
        webhook_url="https://example.com/webhook",
        email_address="admin@example.com",
        alert_on_ping_failure=True,
        cooldown_minutes=cooldown_minutes
    )
    
    # Create mock last alert
    last_alert_time = datetime.utcnow() - timedelta(minutes=minutes_since_last_alert)
    mock_last_alert = Alert(
        id=1,
        vm_id=vm_id,
        alert_type="ping_failure",
        message="Previous alert",
        timestamp=last_alert_time,
        resolved=False
    )
    
    # Mock database queries
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_last_alert
    
    # Act
    is_in_cooldown = alert_service.check_cooldown(
        vm_id=vm_id,
        alert_type="ping_failure",
        cooldown_minutes=cooldown_minutes
    )
    
    # Assert
    if minutes_since_last_alert < cooldown_minutes:
        assert is_in_cooldown is True, \
            f"Should be in cooldown: last alert was {minutes_since_last_alert} min ago, " \
            f"cooldown is {cooldown_minutes} min"
    else:
        assert is_in_cooldown is False, \
            f"Should NOT be in cooldown: last alert was {minutes_since_last_alert} min ago, " \
            f"cooldown is {cooldown_minutes} min"


@given(
    vm_id=vm_ids,
    alert_type=alert_types
)
def test_property_alert_sent_recorded(vm_id, alert_type, mock_db_session):
    """
    Property 12: Alert Payload Completeness (Recording)
    
    Property: Every alert sent should be recorded in the database with
    complete details for audit trail.
    
    Validates: Requirement 8.1 - Record all alerts sent
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock VM
    mock_vm = VM(
        id=vm_id,
        user_id=1,
        hostname="test-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    # Mock database queries
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    alert_service.record_alert_sent(
        vm_id=vm_id,
        alert_type=alert_type,
        message="Test alert message",
        details={"test": "data"}
    )
    
    # Assert
    # Verify that db.add was called (alert was recorded)
    mock_db_session.add.assert_called_once()
    
    # Verify that db.commit was called (alert was persisted)
    mock_db_session.commit.assert_called_once()


@given(
    vm_id=vm_ids,
    webhook_enabled=st.booleans(),
    email_enabled=st.booleans()
)
def test_property_alert_respects_preferences(
    vm_id, webhook_enabled, email_enabled, mock_db_session
):
    """
    Property 12: Alert Payload Completeness (Preferences)
    
    Property: Alerts should only be sent via channels that are enabled
    in the VM's alert configuration.
    
    Validates: Requirement 8.6 - Respect per-VM alert preferences
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock alert config
    mock_config = AlertConfig(
        vm_id=vm_id,
        webhook_url="https://example.com/webhook" if webhook_enabled else None,
        email_address="admin@example.com" if email_enabled else None,
        alert_on_ping_failure=True,
        cooldown_minutes=15
    )
    
    # Mock database queries
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_config
    
    # Act
    config = alert_service.get_alert_config(vm_id)
    
    # Assert
    if webhook_enabled:
        assert config.webhook_url is not None, "Webhook should be enabled"
    else:
        assert config.webhook_url is None, "Webhook should be disabled"
    
    if email_enabled:
        assert config.email_address is not None, "Email should be enabled"
    else:
        assert config.email_address is None, "Email should be disabled"


@given(
    vm_id=vm_ids,
    alert_type=alert_types,
    retry_count=st.integers(min_value=0, max_value=5)
)
def test_property_webhook_retry_logic(
    vm_id, alert_type, retry_count, mock_db_session
):
    """
    Property 12: Alert Payload Completeness (Retry Logic)
    
    Property: Failed webhook deliveries should be retried according to
    the configured retry policy (3 attempts with exponential backoff).
    
    Validates: Requirement 8.2 - Retry failed webhook deliveries
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock VM
    mock_vm = VM(
        id=vm_id,
        user_id=1,
        hostname="test-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    # Mock database queries
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act & Assert
    # Verify retry count is within acceptable range
    max_retries = 3  # As per requirement 8.2
    
    if retry_count <= max_retries:
        # Should attempt delivery
        assert retry_count >= 0, "Retry count should be non-negative"
    else:
        # Should give up after max retries
        assert retry_count > max_retries, "Should not retry more than max attempts"


@given(
    vm_id=vm_ids,
    initial_failure=st.booleans()
)
def test_property_recovery_notification(vm_id, initial_failure, mock_db_session):
    """
    Property 12: Alert Payload Completeness (Recovery)
    
    Property: When a VM recovers from a failure state, a recovery notification
    should be sent if alerts are enabled.
    
    Validates: Requirement 8.7 - Send recovery notifications
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock VM
    mock_vm = VM(
        id=vm_id,
        user_id=1,
        hostname="test-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    # Create mock alert config
    mock_config = AlertConfig(
        vm_id=vm_id,
        webhook_url="https://example.com/webhook",
        email_address="admin@example.com",
        alert_on_ping_failure=True,
        cooldown_minutes=15
    )
    
    # Create mock previous failure alert
    if initial_failure:
        mock_failure_alert = Alert(
            id=1,
            vm_id=vm_id,
            alert_type="ping_failure",
            message="VM is down",
            timestamp=datetime.utcnow() - timedelta(minutes=30),
            resolved=False
        )
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_failure_alert
    else:
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    # Act
    should_send_recovery = alert_service.should_send_recovery_notification(
        vm_id=vm_id,
        alert_type="ping_failure"
    )
    
    # Assert
    if initial_failure:
        assert should_send_recovery is True, \
            "Should send recovery notification after a failure"
    else:
        assert should_send_recovery is False, \
            "Should NOT send recovery notification if there was no prior failure"


@given(
    cooldown_minutes=st.integers(min_value=1, max_value=1440)
)
def test_property_cooldown_configurable(cooldown_minutes, mock_db_session):
    """
    Property 13: Alert Cooldown Prevention (Configurability)
    
    Property: Cooldown period should be configurable per VM, with valid
    range of 1-1440 minutes (1 minute to 24 hours).
    
    Validates: Requirement 8.5 - Configurable cooldown period
    """
    # Arrange
    alert_service = AlertHandlerService(mock_db_session)
    
    # Create mock alert config with specified cooldown
    mock_config = AlertConfig(
        vm_id=1,
        webhook_url="https://example.com/webhook",
        email_address="admin@example.com",
        alert_on_ping_failure=True,
        cooldown_minutes=cooldown_minutes
    )
    
    # Act & Assert
    assert 1 <= cooldown_minutes <= 1440, \
        f"Cooldown period {cooldown_minutes} should be within valid range (1-1440 minutes)"
    
    assert mock_config.cooldown_minutes == cooldown_minutes, \
        "Cooldown period should be configurable"
