"""
Celery tasks for background processing.

This module implements all background tasks for VM monitoring:
- ping_check_task: Execute Custom_Ping for a single VM
- collect_metrics_task: Collect metrics via SSH for a single VM
- schedule_ping_checks: Orchestrator task to dispatch ping checks for all VMs
- schedule_metric_collection: Orchestrator task to dispatch metric collection for all VMs
- cleanup_historical_data: Daily cleanup task for data retention policies
- dns_resolve_task: Resolve hostname to IP and detect drift
- schedule_dns_resolution: Orchestrator task to dispatch DNS resolution for all VMs

Requirements: 4.1, 5.6, 8.1, 9.1-9.5, 15.1-15.6
"""

import logging
import socket
from datetime import datetime
from typing import List

from celery import group
from sqlalchemy.orm import Session

from vmledger.celery_app import celery_app
from vmledger.database import get_db_context
from vmledger.models.vm import VM
from vmledger.models.credential import Credential
from vmledger.services.health_check_service import HealthCheckService, PingResultData
from vmledger.services.metric_collector_service import MetricCollectorService, MetricData
from vmledger.services.alert_handler_service import AlertHandlerService
from vmledger.services.data_cleanup_service import DataCleanupService
from vmledger.services.credential_manager import CredentialManager


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def ping_check_task(self, vm_id: int):
    """
    Execute Custom_Ping check for a single VM.
    
    This task:
    1. Retrieves VM from database
    2. Executes HealthCheckService.execute_ping
    3. Stores ping result
    4. Triggers alert check if ping failed
    
    Args:
        vm_id: VM ID to check
        
    Requirements: 4.1-4.6, 8.1
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting ping check task for VM {vm_id}")
    
    try:
        with get_db_context() as db:
            # Retrieve VM from database
            vm = db.query(VM).filter(VM.id == vm_id).first()
            
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return {
                    'success': False,
                    'vm_id': vm_id,
                    'error': 'VM not found'
                }
            
            # Execute ping check
            health_check_service = HealthCheckService(db)
            ping_result = health_check_service.execute_ping(vm)
            
            # Store ping result
            health_check_service.store_ping_result(vm_id, ping_result)
            
            # Trigger alert check if ping failed
            if not ping_result.success:
                logger.warning(f"Ping failed for VM {vm_id}, checking alert conditions")
                alert_handler = AlertHandlerService(db)
                
                # Check if alert should be triggered
                alert_type = alert_handler.check_alert_conditions(vm, None)
                
                if alert_type:
                    # Send alert with error information
                    error_info = {
                        'error_type': ping_result.error_type
                    }
                    alert_handler.send_alert(vm, alert_type, error_info)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed ping check task for VM {vm_id} in {elapsed:.2f}s: "
                f"success={ping_result.success}"
            )
            
            return {
                'success': True,
                'vm_id': vm_id,
                'ping_success': ping_result.success,
                'response_time_ms': ping_result.response_time_ms,
                'error_type': ping_result.error_type,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Ping check task failed for VM {vm_id} after {elapsed:.2f}s: {exc}"
        )
        
        # Retry with exponential backoff (60 seconds countdown)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def collect_metrics_task(self, vm_id: int):
    """
    Collect resource metrics via SSH for a single VM.
    
    This task:
    1. Retrieves VM and credentials from database
    2. Decrypts credentials using CredentialManager
    3. Executes MetricCollectorService.collect_metrics
    4. Stores metrics result
    
    Args:
        vm_id: VM ID to collect metrics from
        
    Requirements: 5.1-5.7
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting metric collection task for VM {vm_id}")
    
    try:
        with get_db_context() as db:
            # Retrieve VM from database
            vm = db.query(VM).filter(VM.id == vm_id).first()
            
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return {
                    'success': False,
                    'vm_id': vm_id,
                    'error': 'VM not found'
                }
            
            # Collect metrics
            metric_collector_service = MetricCollectorService(db)
            metrics = metric_collector_service.collect_metrics(vm)
            
            # Store metrics result
            metric_collector_service.store_metrics(vm_id, metrics)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed metric collection task for VM {vm_id} in {elapsed:.2f}s: "
                f"success={metrics.collection_success}"
            )
            
            return {
                'success': True,
                'vm_id': vm_id,
                'collection_success': metrics.collection_success,
                'cpu_usage_percent': metrics.cpu_usage_percent,
                'ram_used_mb': metrics.ram_used_mb,
                'disk_usage_percent': metrics.disk_usage_percent,
                'error_message': metrics.error_message,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Metric collection task failed for VM {vm_id} after {elapsed:.2f}s: {exc}"
        )
        
        # Retry with exponential backoff
        # Celery default: 2^attempt * countdown (180s, 360s, 720s)
        raise self.retry(exc=exc, countdown=180)


@celery_app.task
def schedule_ping_checks():
    """
    Orchestrator task to schedule ping checks for all active VMs.
    
    This task:
    1. Queries all active VMs from database
    2. Dispatches ping_check_task for each VM
    3. Implements concurrent processing (10 workers)
    
    Requirements: 9.1-9.5
    """
    start_time = datetime.utcnow()
    logger.info("Starting schedule_ping_checks orchestrator task")
    
    try:
        with get_db_context() as db:
            # Query all VMs (no filtering by is_reachable - check all VMs)
            vms = db.query(VM).all()
            vm_count = len(vms)
            
            if vm_count == 0:
                logger.info("No VMs found to ping")
                return {
                    'success': True,
                    'vms_scheduled': 0,
                    'elapsed_seconds': 0
                }
            
            logger.info(f"Scheduling ping checks for {vm_count} VMs")
            
            # Create group of ping check tasks for concurrent execution
            # Celery will distribute these across available workers
            job = group(
                ping_check_task.s(vm.id) for vm in vms
            )
            
            # Dispatch all tasks
            result = job.apply_async()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Scheduled ping checks for {vm_count} VMs in {elapsed:.2f}s"
            )
            
            return {
                'success': True,
                'vms_scheduled': vm_count,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"schedule_ping_checks failed after {elapsed:.2f}s: {exc}"
        )
        return {
            'success': False,
            'error': str(exc),
            'elapsed_seconds': elapsed
        }


@celery_app.task
def schedule_metric_collection():
    """
    Orchestrator task to schedule metric collection for all active VMs.
    
    This task:
    1. Queries all active VMs from database
    2. Dispatches collect_metrics_task for each VM
    3. Implements concurrent processing (10 workers)
    
    Requirements: 9.1-9.5
    """
    start_time = datetime.utcnow()
    logger.info("Starting schedule_metric_collection orchestrator task")
    
    try:
        with get_db_context() as db:
            # Query all VMs (no filtering - collect metrics for all VMs)
            vms = db.query(VM).all()
            vm_count = len(vms)
            
            if vm_count == 0:
                logger.info("No VMs found for metric collection")
                return {
                    'success': True,
                    'vms_scheduled': 0,
                    'elapsed_seconds': 0
                }
            
            logger.info(f"Scheduling metric collection for {vm_count} VMs")
            
            # Create group of metric collection tasks for concurrent execution
            # Celery will distribute these across available workers
            job = group(
                collect_metrics_task.s(vm.id) for vm in vms
            )
            
            # Dispatch all tasks
            result = job.apply_async()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Scheduled metric collection for {vm_count} VMs in {elapsed:.2f}s"
            )
            
            return {
                'success': True,
                'vms_scheduled': vm_count,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"schedule_metric_collection failed after {elapsed:.2f}s: {exc}"
        )
        return {
            'success': False,
            'error': str(exc),
            'elapsed_seconds': elapsed
        }


@celery_app.task
def cleanup_historical_data():
    """
    Daily cleanup task for data retention policies.
    
    This task:
    1. Calls DataCleanupService.cleanup_all()
    2. Logs cleanup statistics
    
    Scheduled to run daily at 2 AM UTC.
    
    Requirements: 4.6, 5.7
    """
    start_time = datetime.utcnow()
    logger.info("Starting cleanup_historical_data task")
    
    try:
        with get_db_context() as db:
            # Execute cleanup
            cleanup_service = DataCleanupService(db)
            stats = cleanup_service.cleanup_all()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed cleanup_historical_data task in {elapsed:.2f}s: "
                f"ping_results={stats.ping_results_deleted}, "
                f"metrics={stats.metrics_deleted}, "
                f"alerts={stats.alerts_deleted}"
            )
            
            return {
                'success': True,
                'ping_results_deleted': stats.ping_results_deleted,
                'metrics_deleted': stats.metrics_deleted,
                'alerts_deleted': stats.alerts_deleted,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"cleanup_historical_data task failed after {elapsed:.2f}s: {exc}"
        )
        return {
            'success': False,
            'error': str(exc),
            'elapsed_seconds': elapsed
        }


@celery_app.task(bind=True, max_retries=2)
def dns_resolve_task(self, vm_id: int):
    """
    Resolve hostname to IP address for a single VM and detect drift.
    
    This task:
    1. Retrieves VM from database
    2. Resolves hostname via DNS (socket.getaddrinfo)
    3. Compares resolved IP with stored ip_address
    4. Updates resolved_ip, dns_last_checked, and dns_mismatch fields
    
    Args:
        vm_id: VM ID to resolve
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting DNS resolution task for VM {vm_id}")
    
    try:
        with get_db_context() as db:
            vm = db.query(VM).filter(VM.id == vm_id).first()
            
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return {
                    'success': False,
                    'vm_id': vm_id,
                    'error': 'VM not found'
                }
            
            hostname = vm.hostname
            domain = vm.domain
            stored_ip = vm.ip_address
            resolved_ip = None
            dns_mismatch = False
            error_msg = None
            
            # Use domain (FQDN) if available, otherwise fallback to hostname
            target_name = domain if domain else hostname
            
            try:
                # Resolve hostname to IP address
                # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
                results = socket.getaddrinfo(target_name, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
                if results:
                    # Take the first result's IP address
                    resolved_ip = results[0][4][0]
                    dns_mismatch = (resolved_ip != stored_ip)
                    
                    if dns_mismatch:
                        logger.warning(
                            f"DNS mismatch for VM {vm_id} ({hostname}): "
                            f"stored={stored_ip}, resolved={resolved_ip}"
                        )
                    else:
                        logger.info(
                            f"DNS resolved for VM {vm_id} ({hostname}): "
                            f"IP matches ({resolved_ip})"
                        )
                else:
                    error_msg = f"No DNS results for hostname: {hostname}"
                    logger.warning(error_msg)
                    
            except socket.gaierror as e:
                error_msg = f"DNS resolution failed for {hostname}: {e}"
                logger.warning(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error resolving {hostname}: {e}"
                logger.error(error_msg)
            
            # Update VM record
            vm.dns_last_checked = datetime.utcnow()
            if resolved_ip:
                vm.resolved_ip = resolved_ip
                vm.dns_mismatch = dns_mismatch
            
            db.commit()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed DNS resolution task for VM {vm_id} in {elapsed:.2f}s"
            )
            
            return {
                'success': True,
                'vm_id': vm_id,
                'hostname': hostname,
                'stored_ip': stored_ip,
                'resolved_ip': resolved_ip,
                'dns_mismatch': dns_mismatch,
                'error': error_msg,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"DNS resolution task failed for VM {vm_id} after {elapsed:.2f}s: {exc}"
        )
        raise self.retry(exc=exc, countdown=120)


@celery_app.task
def schedule_dns_resolution():
    """
    Orchestrator task to schedule DNS resolution for all VMs.
    
    Runs every 6 hours. For each VM, resolves the hostname and
    compares the result against the stored IP address to detect drift.
    """
    start_time = datetime.utcnow()
    logger.info("Starting schedule_dns_resolution orchestrator task")
    
    try:
        with get_db_context() as db:
            vms = db.query(VM).all()
            vm_count = len(vms)
            
            if vm_count == 0:
                logger.info("No VMs found for DNS resolution")
                return {
                    'success': True,
                    'vms_scheduled': 0,
                    'elapsed_seconds': 0
                }
            
            logger.info(f"Scheduling DNS resolution for {vm_count} VMs")
            
            job = group(
                dns_resolve_task.s(vm.id) for vm in vms
            )
            
            result = job.apply_async()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Scheduled DNS resolution for {vm_count} VMs in {elapsed:.2f}s"
            )
            
            return {
                'success': True,
                'vms_scheduled': vm_count,
                'elapsed_seconds': elapsed
            }
            
    except Exception as exc:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"schedule_dns_resolution failed after {elapsed:.2f}s: {exc}"
        )
        return {
            'success': False,
            'error': str(exc),
            'elapsed_seconds': elapsed
        }
