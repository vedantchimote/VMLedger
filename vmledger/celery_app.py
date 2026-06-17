"""
Celery application configuration for background task processing.
"""

from celery import Celery
from celery.schedules import crontab
import logging

from vmledger.config import settings

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "vmledger",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["vmledger.tasks"]  # Import tasks module
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,  # Reject tasks if worker dies
    task_track_started=True,  # Track when tasks start
    
    # Task timeout settings
    task_soft_time_limit=60,  # Soft timeout for ping tasks
    task_time_limit=120,  # Hard timeout for all tasks
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster" if settings.redis_password else None
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    
    # Rate limiting
    task_default_rate_limit="50/s",  # 50 tasks per second per worker
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "ping-all-vms": {
        "task": "vmledger.tasks.schedule_ping_checks",
        "schedule": 60.0,  # Run orchestrator every 1 minute
        "options": {
            "expires": 55  # Expire before next run
        }
    },
    "collect-all-metrics": {
        "task": "vmledger.tasks.schedule_metric_collection",
        "schedule": float(settings.metrics_interval_seconds),
        "options": {
            "expires": settings.metrics_interval_seconds - 5
        }
    },
    "cleanup-old-data": {
        "task": "vmledger.tasks.cleanup_historical_data",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM UTC
    },
    "dns-resolve-all-vms": {
        "task": "vmledger.tasks.schedule_dns_resolution",
        "schedule": 3600.0,  # Run orchestrator every 1 hour
        "options": {
            "expires": 3500
        }
    },
}


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks after Celery is configured."""
    logger.info("Celery periodic tasks configured")
    logger.info(f"Ping interval: {settings.ping_interval_seconds}s")
    logger.info(f"Metrics interval: {settings.metrics_interval_seconds}s")
    logger.info(f"Concurrent workers: {settings.concurrent_workers}")


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery configuration."""
    logger.info(f"Request: {self.request!r}")
    return {"status": "success", "message": "Debug task executed"}
