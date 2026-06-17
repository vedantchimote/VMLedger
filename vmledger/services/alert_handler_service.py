"""
Alert Handler Service for dispatching notifications when VMs become unreachable.

This service manages alert conditions, cooldown logic, and notification dispatch
via webhooks and email. It supports retry logic for webhooks and respects
per-VM alert preferences.

Requirements: 8.1-8.7
"""

import logging
import time
import json
import smtplib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from sqlalchemy.orm import Session

from vmledger.models.vm import VM
from vmledger.models.alert import Alert
from vmledger.models.alert_config import AlertConfig
from vmledger.models.ping_result import PingResult
from vmledger.config import settings
from vmledger.exceptions import (
    AlertHandlerServiceError,
    AlertDeliveryError
)


logger = logging.getLogger(__name__)


class WebhookError(AlertHandlerServiceError):
    """Raised when webhook notification fails."""
    pass


class EmailError(AlertHandlerServiceError):
    """Raised when email notification fails."""
    pass


class AlertHandlerService:
    """
    Manages alert notifications for VM health status changes.
    
    Implements alert condition checking, cooldown logic, and notification
    dispatch via webhooks and email with retry logic.
    """
    
    # Alert type constants
    ALERT_VM_UNREACHABLE = "VM_UNREACHABLE"
    ALERT_VM_RECOVERED = "VM_RECOVERED"
    ALERT_METRICS_UNAVAILABLE = "METRICS_UNAVAILABLE"
    ALERT_DNS_DRIFT = "DNS_DRIFT"
    
    # Notification method constants
    METHOD_WEBHOOK = "webhook"
    METHOD_EMAIL = "email"
    
    def __init__(self, db: Session):
        """
        Initialize the alert handler service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.cooldown_minutes = settings.alert_cooldown_minutes
        
        # Webhook retry configuration
        self.webhook_max_retries = 3
        self.webhook_retry_delays = [5, 15, 45]  # Exponential backoff in seconds
        self.webhook_timeout = 30  # seconds
        
        # SMTP configuration
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_from_email = settings.smtp_from_email
        self.smtp_use_tls = settings.smtp_use_tls
    
    def check_alert_conditions(
        self,
        vm: VM,
        ping_result: Optional[PingResult] = None
    ) -> Optional[str]:
        """
        Determine if an alert should be triggered based on VM status.
        
        Checks if VM status has changed and determines the appropriate alert type.
        
        Args:
            vm: VM object to check
            ping_result: Latest ping result (optional)
            
        Returns:
            Alert type string if alert should be triggered, None otherwise
            
        Requirements: 8.1 - Trigger notification when VM fails Custom_Ping check
        Requirements: 8.6 - Send recovery notification when VM becomes reachable
        """
        # Get alert configuration for this VM
        alert_config = self.db.query(AlertConfig).filter(
            AlertConfig.vm_id == vm.id
        ).first()
        
        # If alerts are disabled for this VM, don't trigger
        if not alert_config or not alert_config.enabled:
            logger.debug(f"Alerts disabled for VM {vm.id}")
            return None
        
        # Determine alert type based on ping result
        if ping_result:
            if not ping_result.success and vm.is_reachable is not False:
                # VM just became unreachable
                logger.info(f"VM {vm.id} became unreachable")
                return self.ALERT_VM_UNREACHABLE
            elif ping_result.success and vm.is_reachable is False:
                # VM recovered
                logger.info(f"VM {vm.id} recovered")
                return self.ALERT_VM_RECOVERED
        
        return None
    
    def check_cooldown(self, vm_id: int, alert_type: str) -> bool:
        """
        Check if alert is in cooldown period.
        
        Prevents duplicate alerts for the same VM within the cooldown window.
        
        Args:
            vm_id: VM ID
            alert_type: Type of alert to check
            
        Returns:
            True if alert can be sent (not in cooldown), False if in cooldown
            
        Requirements: 8.5 - Prevent duplicate alerts within 15-minute window
        """
        try:
            # Calculate cooldown threshold
            cooldown_threshold = datetime.utcnow() - timedelta(
                minutes=self.cooldown_minutes
            )
            
            # Check for recent alerts of the same type
            recent_alert = (
                self.db.query(Alert)
                .filter(
                    Alert.vm_id == vm_id,
                    Alert.alert_type == alert_type,
                    Alert.sent_at >= cooldown_threshold,
                    Alert.success == True  # Only count successful alerts
                )
                .order_by(Alert.sent_at.desc())
                .first()
            )
            
            if recent_alert:
                time_since_alert = datetime.utcnow() - recent_alert.sent_at
                logger.debug(
                    f"VM {vm_id} alert type {alert_type} in cooldown "
                    f"(last sent {time_since_alert.total_seconds():.0f}s ago)"
                )
                return False
            
            logger.debug(f"VM {vm_id} alert type {alert_type} not in cooldown")
            return True
            
        except Exception as e:
            logger.error(f"Error checking cooldown for VM {vm_id}: {e}")
            # On error, allow alert to be sent (fail open)
            return True
    
    def _format_webhook_payload(
        self,
        vm: VM,
        alert_type: str,
        error_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format webhook payload with VM details.
        
        Args:
            vm: VM object
            alert_type: Type of alert
            error_info: Optional error information
            
        Returns:
            Dictionary with webhook payload
            
        Requirements: 8.4 - Include VM hostname, IP address, and failure timestamp
        """
        payload = {
            "event": alert_type.lower(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "vm": {
                "id": vm.id,
                "hostname": vm.hostname,
                "ip_address": vm.ip_address,
                "ssh_port": vm.ssh_port
            }
        }
        
        # Add details section
        details = {}
        
        if error_info:
            details.update(error_info)
        
        if vm.last_seen:
            details["last_seen"] = vm.last_seen.isoformat() + "Z"
        
        if details:
            payload["details"] = details
        
        return payload
    
    def _format_email_body(
        self,
        vm: VM,
        alert_type: str,
        error_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format email body with VM details.
        
        Args:
            vm: VM object
            alert_type: Type of alert
            error_info: Optional error information
            
        Returns:
            Formatted email body text
            
        Requirements: 8.4 - Include VM hostname, IP address, and failure timestamp
        """
        # Determine status text
        if alert_type == self.ALERT_VM_UNREACHABLE:
            status = "UNREACHABLE"
        elif alert_type == self.ALERT_VM_RECOVERED:
            status = "RECOVERED"
        elif alert_type == self.ALERT_METRICS_UNAVAILABLE:
            status = "METRICS UNAVAILABLE"
        elif alert_type == self.ALERT_DNS_DRIFT:
            status = "DNS DRIFT DETECTED"
        else:
            status = "UNKNOWN"
        
        # Build email body
        lines = [
            f"VM Details:",
            f"- Hostname: {vm.hostname}",
            f"- IP Address: {vm.ip_address}",
            f"- SSH Port: {vm.ssh_port}",
            f"- Status: {status}",
            f"- Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        
        # Add error information if available
        if error_info:
            if "error_type" in error_info:
                lines.append(f"- Error: {error_info['error_type']}")
        
        # Add last seen timestamp
        if vm.last_seen:
            lines.append(
                f"\nLast successful check: "
                f"{vm.last_seen.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        
        # Add dashboard link (placeholder - would be configured in production)
        lines.append(f"\nView in dashboard: http://localhost:3000/vms/{vm.id}")
        
        return "\n".join(lines)
    
    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Send webhook notification with retry logic.
        
        Implements exponential backoff retry strategy:
        - Attempt 1: immediate
        - Attempt 2: 5 seconds delay
        - Attempt 3: 15 seconds delay
        - Attempt 4: 45 seconds delay
        
        Args:
            url: Webhook URL
            payload: JSON payload to send
            
        Returns:
            True if webhook sent successfully, False otherwise
            
        Requirements: 8.2 - Support webhook-based notifications
        Requirements: Design - Retry logic: 3 attempts with exponential backoff
        """
        last_error = None
        
        for attempt in range(1, self.webhook_max_retries + 1):
            try:
                logger.debug(
                    f"Webhook attempt {attempt}/{self.webhook_max_retries} to {url}"
                )
                
                # Send POST request
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.webhook_timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                # Check response status
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook sent successfully to {url} "
                        f"(status {response.status_code}, attempt {attempt})"
                    )
                    return True
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        f"Webhook attempt {attempt} failed: {last_error}"
                    )
                    
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                logger.warning(
                    f"Webhook attempt {attempt} timed out after "
                    f"{self.webhook_timeout}s"
                )
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(f"Webhook attempt {attempt} failed: {e}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error sending webhook: {e}")
                break
            
            # Wait before retry (except on last attempt)
            if attempt < self.webhook_max_retries:
                delay = self.webhook_retry_delays[attempt - 1]
                logger.debug(f"Waiting {delay}s before retry...")
                time.sleep(delay)
        
        # All retries failed
        logger.error(
            f"Failed to send webhook after {self.webhook_max_retries} attempts: "
            f"{last_error}"
        )
        return False
    
    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str
    ) -> bool:
        """
        Send email notification using SMTP.
        
        Args:
            recipient: Email recipient address
            subject: Email subject
            body: Email body text
            
        Returns:
            True if email sent successfully, False otherwise
            
        Requirements: 8.3 - Support email-based notifications
        """
        # Check if SMTP is configured
        if not self.smtp_host or not self.smtp_username:
            logger.warning("SMTP not configured, skipping email notification")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from_email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Attach body
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            logger.debug(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}")
            
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            # Login if credentials provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {recipient}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return False
    
    def record_alert_sent(
        self,
        vm_id: int,
        alert_type: str,
        notification_method: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record alert notification in database.
        
        Args:
            vm_id: VM ID
            alert_type: Type of alert
            notification_method: 'webhook' or 'email'
            success: Whether notification was sent successfully
            error_message: Error message if failed
            
        Requirements: Design - Store alert history in alerts table
        """
        try:
            alert = Alert(
                vm_id=vm_id,
                alert_type=alert_type,
                sent_at=datetime.utcnow(),
                notification_method=notification_method,
                success=success,
                error_message=error_message
            )
            
            self.db.add(alert)
            self.db.commit()
            
            logger.debug(
                f"Recorded alert for VM {vm_id}: "
                f"type={alert_type}, method={notification_method}, success={success}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record alert for VM {vm_id}: {e}")
            self.db.rollback()
            # Don't raise exception - recording failure shouldn't block alert dispatch
    
    def send_alert(
        self,
        vm: VM,
        alert_type: str,
        error_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Orchestrate alert notification dispatch.
        
        Sends notifications via configured methods (webhook and/or email)
        and records alert history.
        
        Args:
            vm: VM object
            alert_type: Type of alert
            error_info: Optional error information
            
        Requirements: 8.1 - Trigger notification when VM fails Custom_Ping
        Requirements: 8.2 - Support webhook-based notifications
        Requirements: 8.3 - Support email-based notifications
        Requirements: 8.4 - Include VM hostname, IP address, and failure timestamp
        Requirements: 8.5 - Prevent duplicate alerts within 15-minute window
        Requirements: 8.6 - Send recovery notification when VM becomes reachable
        Requirements: 8.7 - Respect per-VM alert preferences
        """
        logger.info(f"Sending alert for VM {vm.id}: type={alert_type}")
        
        # Get alert configuration
        alert_config = self.db.query(AlertConfig).filter(
            AlertConfig.vm_id == vm.id
        ).first()
        
        if not alert_config or not alert_config.enabled:
            logger.debug(f"Alerts disabled for VM {vm.id}, skipping")
            return
        
        # Check cooldown
        if not self.check_cooldown(vm.id, alert_type):
            logger.info(
                f"Alert for VM {vm.id} in cooldown period, skipping"
            )
            return
        
        # Format subject for email
        if alert_type == self.ALERT_VM_UNREACHABLE:
            subject = f"[VMLedger Alert] {vm.hostname} is UNREACHABLE"
        elif alert_type == self.ALERT_VM_RECOVERED:
            subject = f"[VMLedger Alert] {vm.hostname} has RECOVERED"
        elif alert_type == self.ALERT_METRICS_UNAVAILABLE:
            subject = f"[VMLedger Alert] {vm.hostname} metrics UNAVAILABLE"
        elif alert_type == self.ALERT_DNS_DRIFT:
            subject = f"[VMLedger Alert] {vm.hostname} DNS drift detected"
        else:
            subject = f"[VMLedger Alert] {vm.hostname} status changed"
        
        # Send webhook if configured
        if alert_config.webhook_url:
            payload = self._format_webhook_payload(vm, alert_type, error_info)
            webhook_success = self.send_webhook(alert_config.webhook_url, payload)
            
            # Record webhook alert
            self.record_alert_sent(
                vm.id,
                alert_type,
                self.METHOD_WEBHOOK,
                webhook_success,
                None if webhook_success else "Webhook delivery failed"
            )
        
        # Send email if configured
        if alert_config.email_recipient:
            body = self._format_email_body(vm, alert_type, error_info)
            email_success = self.send_email(
                alert_config.email_recipient,
                subject,
                body
            )
            
            # Record email alert
            self.record_alert_sent(
                vm.id,
                alert_type,
                self.METHOD_EMAIL,
                email_success,
                None if email_success else "Email delivery failed"
            )
        
        logger.info(f"Alert dispatch completed for VM {vm.id}")
