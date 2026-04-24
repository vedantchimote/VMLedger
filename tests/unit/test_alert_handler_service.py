"""
Unit tests for AlertHandlerService.

Tests alert condition checking, cooldown logic, webhook/email dispatch,
and alert history recording.

Requirements: 8.1-8.7
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import smtplib

from sqlalchemy.orm import Session

from vmledger.services.alert_handler_service import AlertHandlerService
from vmledger.models.vm import VM
from vmledger.models.alert import Alert
from vmledger.models.alert_config import AlertConfig
from vmledger.models.ping_result import PingResult
from vmledger.models.user import User


@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def alert_service(db_session):
    """Create AlertHandlerService instance."""
    return AlertHandlerService(db_session)


@pytest.fixture
def test_user():
    """Create test user."""
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hashed",
        encryption_salt="salt123"
    )
    return user


@pytest.fixture
def test_vm(test_user):
    """Create test VM."""
    vm = VM(
        id=1,
        user_id=test_user.id,
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        is_reachable=True,
        last_seen=datetime.utcnow()
    )
    return vm


@pytest.fixture
def test_alert_config(test_vm):
    """Create test alert configuration."""
    config = AlertConfig(
        id=1,
        vm_id=test_vm.id,
        enabled=True,
        webhook_url="https://webhook.example.com/alert",
        email_recipient="admin@example.com",
        cooldown_minutes=15
    )
    return config


class TestCheckAlertConditions:
    """Test alert condition checking."""
    
    def test_vm_becomes_unreachable(self, alert_service, db_session, test_vm, test_alert_config):
        """Test alert triggered when VM becomes unreachable."""
        # Setup
        test_vm.is_reachable = True
        ping_result = PingResult(
            vm_id=test_vm.id,
            success=False,
            error_type="TIMEOUT"
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        
        # Execute
        alert_type = alert_service.check_alert_conditions(test_vm, ping_result)
        
        # Verify
        assert alert_type == AlertHandlerService.ALERT_VM_UNREACHABLE
    
    def test_vm_recovers(self, alert_service, db_session, test_vm, test_alert_config):
        """Test alert triggered when VM recovers."""
        # Setup
        test_vm.is_reachable = False
        ping_result = PingResult(
            vm_id=test_vm.id,
            success=True,
            response_time_ms=50.0
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        
        # Execute
        alert_type = alert_service.check_alert_conditions(test_vm, ping_result)
        
        # Verify
        assert alert_type == AlertHandlerService.ALERT_VM_RECOVERED
    
    def test_no_alert_when_disabled(self, alert_service, db_session, test_vm, test_alert_config):
        """Test no alert when alerts are disabled."""
        # Setup
        test_alert_config.enabled = False
        test_vm.is_reachable = True
        ping_result = PingResult(
            vm_id=test_vm.id,
            success=False,
            error_type="TIMEOUT"
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        
        # Execute
        alert_type = alert_service.check_alert_conditions(test_vm, ping_result)
        
        # Verify
        assert alert_type is None
    
    def test_no_alert_when_status_unchanged(self, alert_service, db_session, test_vm, test_alert_config):
        """Test no alert when VM status hasn't changed."""
        # Setup
        test_vm.is_reachable = False
        ping_result = PingResult(
            vm_id=test_vm.id,
            success=False,
            error_type="TIMEOUT"
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        
        # Execute
        alert_type = alert_service.check_alert_conditions(test_vm, ping_result)
        
        # Verify
        assert alert_type is None


class TestCheckCooldown:
    """Test alert cooldown logic."""
    
    def test_cooldown_active_within_15_minutes(self, alert_service, db_session, test_vm):
        """Test cooldown prevents alert within 15-minute window."""
        # Setup - recent alert sent 10 minutes ago
        recent_alert = Alert(
            vm_id=test_vm.id,
            alert_type=AlertHandlerService.ALERT_VM_UNREACHABLE,
            sent_at=datetime.utcnow() - timedelta(minutes=10),
            success=True
        )
        
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = recent_alert
        
        # Execute
        can_send = alert_service.check_cooldown(test_vm.id, AlertHandlerService.ALERT_VM_UNREACHABLE)
        
        # Verify
        assert can_send is False
    
    def test_cooldown_expired_after_15_minutes(self, alert_service, db_session, test_vm):
        """Test cooldown allows alert after 15-minute window."""
        # Setup - alert sent 20 minutes ago (outside cooldown window)
        # No recent alert should be found
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Execute
        can_send = alert_service.check_cooldown(test_vm.id, AlertHandlerService.ALERT_VM_UNREACHABLE)
        
        # Verify
        assert can_send is True
    
    def test_no_cooldown_when_no_recent_alerts(self, alert_service, db_session, test_vm):
        """Test no cooldown when no recent alerts exist."""
        # Setup - no recent alerts
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Execute
        can_send = alert_service.check_cooldown(test_vm.id, AlertHandlerService.ALERT_VM_UNREACHABLE)
        
        # Verify
        assert can_send is True
    
    def test_cooldown_ignores_failed_alerts(self, alert_service, db_session, test_vm):
        """Test cooldown only counts successful alerts."""
        # Setup - no successful alerts found (failed alerts are filtered out by query)
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Execute
        can_send = alert_service.check_cooldown(test_vm.id, AlertHandlerService.ALERT_VM_UNREACHABLE)
        
        # Verify
        # Should allow alert since no successful alert was found
        assert can_send is True


class TestWebhookPayloadFormatting:
    """Test webhook payload formatting."""
    
    def test_payload_includes_vm_details(self, alert_service, test_vm):
        """Test webhook payload includes VM hostname, IP, and port."""
        # Execute
        payload = alert_service._format_webhook_payload(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify
        assert payload["event"] == "vm_unreachable"
        assert "timestamp" in payload
        assert payload["vm"]["id"] == test_vm.id
        assert payload["vm"]["hostname"] == test_vm.hostname
        assert payload["vm"]["ip_address"] == test_vm.ip_address
        assert payload["vm"]["ssh_port"] == test_vm.ssh_port
    
    def test_payload_includes_last_seen(self, alert_service, test_vm):
        """Test webhook payload includes last_seen timestamp."""
        # Setup
        test_vm.last_seen = datetime(2024, 1, 15, 10, 30, 0)
        
        # Execute
        payload = alert_service._format_webhook_payload(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify
        assert "details" in payload
        assert "last_seen" in payload["details"]
    
    def test_payload_includes_error_info(self, alert_service, test_vm):
        """Test webhook payload includes error information."""
        # Execute
        error_info = {"error_type": "TIMEOUT"}
        payload = alert_service._format_webhook_payload(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE,
            error_info
        )
        
        # Verify
        assert "details" in payload
        assert payload["details"]["error_type"] == "TIMEOUT"


class TestEmailFormatting:
    """Test email body formatting."""
    
    def test_email_includes_vm_details(self, alert_service, test_vm):
        """Test email includes VM hostname, IP, and status."""
        # Execute
        body = alert_service._format_email_body(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify
        assert test_vm.hostname in body
        assert test_vm.ip_address in body
        assert "UNREACHABLE" in body
        assert str(test_vm.ssh_port) in body
    
    def test_email_includes_last_seen(self, alert_service, test_vm):
        """Test email includes last successful check timestamp."""
        # Setup
        test_vm.last_seen = datetime(2024, 1, 15, 10, 30, 0)
        
        # Execute
        body = alert_service._format_email_body(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify
        assert "Last successful check" in body
    
    def test_email_includes_error_type(self, alert_service, test_vm):
        """Test email includes error type when provided."""
        # Execute
        error_info = {"error_type": "TIMEOUT"}
        body = alert_service._format_email_body(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE,
            error_info
        )
        
        # Verify
        assert "TIMEOUT" in body


class TestSendWebhook:
    """Test webhook sending with retry logic."""
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    def test_webhook_success_first_attempt(self, mock_post, alert_service):
        """Test webhook succeeds on first attempt."""
        # Setup
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        payload = {"event": "test"}
        url = "https://webhook.example.com/alert"
        
        # Execute
        success = alert_service.send_webhook(url, payload)
        
        # Verify
        assert success is True
        assert mock_post.call_count == 1
        mock_post.assert_called_with(
            url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    @patch('vmledger.services.alert_handler_service.time.sleep')
    def test_webhook_retry_on_failure(self, mock_sleep, mock_post, alert_service):
        """Test webhook retries on failure with exponential backoff."""
        # Setup - fail twice, succeed on third attempt
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Internal Server Error"
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        
        mock_post.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]
        
        payload = {"event": "test"}
        url = "https://webhook.example.com/alert"
        
        # Execute
        success = alert_service.send_webhook(url, payload)
        
        # Verify
        assert success is True
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        # Verify exponential backoff delays
        mock_sleep.assert_any_call(5)
        mock_sleep.assert_any_call(15)
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    @patch('vmledger.services.alert_handler_service.time.sleep')
    def test_webhook_fails_after_max_retries(self, mock_sleep, mock_post, alert_service):
        """Test webhook fails after maximum retries."""
        # Setup - all attempts fail
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        payload = {"event": "test"}
        url = "https://webhook.example.com/alert"
        
        # Execute
        success = alert_service.send_webhook(url, payload)
        
        # Verify
        assert success is False
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    def test_webhook_handles_timeout(self, mock_post, alert_service):
        """Test webhook handles timeout exception."""
        # Setup
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        payload = {"event": "test"}
        url = "https://webhook.example.com/alert"
        
        # Execute
        success = alert_service.send_webhook(url, payload)
        
        # Verify
        assert success is False


class TestSendEmail:
    """Test email sending."""
    
    @patch('vmledger.services.alert_handler_service.smtplib.SMTP')
    def test_email_success(self, mock_smtp_class, alert_service):
        """Test email sent successfully."""
        # Setup
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        alert_service.smtp_host = "smtp.example.com"
        alert_service.smtp_username = "user@example.com"
        alert_service.smtp_password = "password"
        
        # Execute
        success = alert_service.send_email(
            "admin@example.com",
            "Test Alert",
            "Test body"
        )
        
        # Verify
        assert success is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
    
    def test_email_skipped_when_not_configured(self, alert_service):
        """Test email skipped when SMTP not configured."""
        # Setup
        alert_service.smtp_host = ""
        alert_service.smtp_username = ""
        
        # Execute
        success = alert_service.send_email(
            "admin@example.com",
            "Test Alert",
            "Test body"
        )
        
        # Verify
        assert success is False
    
    @patch('vmledger.services.alert_handler_service.smtplib.SMTP')
    def test_email_handles_smtp_error(self, mock_smtp_class, alert_service):
        """Test email handles SMTP errors gracefully."""
        # Setup
        mock_smtp_class.side_effect = smtplib.SMTPException("Connection failed")
        
        alert_service.smtp_host = "smtp.example.com"
        alert_service.smtp_username = "user@example.com"
        
        # Execute
        success = alert_service.send_email(
            "admin@example.com",
            "Test Alert",
            "Test body"
        )
        
        # Verify
        assert success is False


class TestRecordAlertSent:
    """Test alert history recording."""
    
    def test_record_successful_alert(self, alert_service, db_session, test_vm):
        """Test recording successful alert."""
        # Execute
        alert_service.record_alert_sent(
            test_vm.id,
            AlertHandlerService.ALERT_VM_UNREACHABLE,
            AlertHandlerService.METHOD_WEBHOOK,
            True,
            None
        )
        
        # Verify
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        
        # Check alert object
        alert = db_session.add.call_args[0][0]
        assert isinstance(alert, Alert)
        assert alert.vm_id == test_vm.id
        assert alert.alert_type == AlertHandlerService.ALERT_VM_UNREACHABLE
        assert alert.notification_method == AlertHandlerService.METHOD_WEBHOOK
        assert alert.success is True
        assert alert.error_message is None
    
    def test_record_failed_alert(self, alert_service, db_session, test_vm):
        """Test recording failed alert."""
        # Execute
        alert_service.record_alert_sent(
            test_vm.id,
            AlertHandlerService.ALERT_VM_UNREACHABLE,
            AlertHandlerService.METHOD_EMAIL,
            False,
            "SMTP connection failed"
        )
        
        # Verify
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        
        # Check alert object
        alert = db_session.add.call_args[0][0]
        assert alert.success is False
        assert alert.error_message == "SMTP connection failed"


class TestSendAlert:
    """Test complete alert orchestration."""
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    def test_send_alert_with_webhook(self, mock_post, alert_service, db_session, test_vm, test_alert_config):
        """Test alert sent via webhook."""
        # Setup
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Execute
        alert_service.send_alert(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE,
            {"error_type": "TIMEOUT"}
        )
        
        # Verify webhook was called
        assert mock_post.call_count == 1
        call_args = mock_post.call_args
        assert call_args[1]['json']['event'] == 'vm_unreachable'
        assert call_args[1]['json']['vm']['hostname'] == test_vm.hostname
    
    @patch('vmledger.services.alert_handler_service.smtplib.SMTP')
    def test_send_alert_with_email(self, mock_smtp_class, alert_service, db_session, test_vm, test_alert_config):
        """Test alert sent via email."""
        # Setup
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        alert_service.smtp_host = "smtp.example.com"
        alert_service.smtp_username = "user@example.com"
        alert_service.smtp_password = "password"
        
        # Remove webhook URL to test email only
        test_alert_config.webhook_url = None
        
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Execute
        alert_service.send_alert(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify email was sent
        mock_server.send_message.assert_called_once()
    
    @patch('vmledger.services.alert_handler_service.requests.post')
    def test_send_alert_respects_cooldown(self, mock_post, alert_service, db_session, test_vm, test_alert_config):
        """Test alert respects cooldown period."""
        # Setup - recent alert within cooldown
        recent_alert = Alert(
            vm_id=test_vm.id,
            alert_type=AlertHandlerService.ALERT_VM_UNREACHABLE,
            sent_at=datetime.utcnow() - timedelta(minutes=5),
            success=True
        )
        
        # Mock database queries - need to handle multiple filter calls
        def filter_side_effect(*args, **kwargs):
            mock_result = Mock()
            # First filter call is for alert_config
            if not hasattr(filter_side_effect, 'call_count'):
                filter_side_effect.call_count = 0
            
            filter_side_effect.call_count += 1
            
            if filter_side_effect.call_count == 1:
                # First call: get alert_config
                mock_result.first.return_value = test_alert_config
            else:
                # Second call: get recent alert (for cooldown check)
                mock_result.order_by.return_value.first.return_value = recent_alert
            
            return mock_result
        
        db_session.query.return_value.filter.side_effect = filter_side_effect
        
        # Execute
        alert_service.send_alert(
            test_vm,
            AlertHandlerService.ALERT_VM_UNREACHABLE
        )
        
        # Verify no webhook was sent due to cooldown
        mock_post.assert_not_called()
    
    def test_send_alert_skipped_when_disabled(self, alert_service, db_session, test_vm, test_alert_config):
        """Test alert skipped when disabled in config."""
        # Setup
        test_alert_config.enabled = False
        
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.return_value = test_alert_config
        
        # Execute
        with patch('vmledger.services.alert_handler_service.requests.post') as mock_post:
            alert_service.send_alert(
                test_vm,
                AlertHandlerService.ALERT_VM_UNREACHABLE
            )
            
            # Verify no webhook was sent
            mock_post.assert_not_called()
