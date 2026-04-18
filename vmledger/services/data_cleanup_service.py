"""
Data Cleanup Service for managing data retention policies.

This service implements data retention policies using PostgreSQL window functions
to efficiently clean up old monitoring data while preserving recent history.

Requirements: 4.6, 5.7
"""

import logging
from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

from vmledger.exceptions import DataCleanupServiceError

logger = logging.getLogger(__name__)


class CleanupStats:
    """Data class for cleanup operation statistics."""
    
    def __init__(
        self,
        ping_results_deleted: int = 0,
        metrics_deleted: int = 0,
        alerts_deleted: int = 0
    ):
        self.ping_results_deleted = ping_results_deleted
        self.metrics_deleted = metrics_deleted
        self.alerts_deleted = alerts_deleted
    
    def to_dict(self) -> Dict[str, int]:
        """Convert stats to dictionary."""
        return {
            'ping_results_deleted': self.ping_results_deleted,
            'metrics_deleted': self.metrics_deleted,
            'alerts_deleted': self.alerts_deleted
        }


class DataCleanupService:
    """
    Manages data retention policies for monitoring data.
    
    Implements efficient cleanup using PostgreSQL window functions to:
    - Retain last 100 ping results per VM (FIFO queue)
    - Retain last 1000 metrics per VM
    - Retain alerts for 90 days
    """
    
    # Retention limits
    PING_RESULTS_RETENTION = 100  # Keep last 100 per VM
    METRICS_RETENTION = 1000      # Keep last 1000 per VM
    ALERTS_RETENTION_DAYS = 90    # Keep for 90 days
    
    def __init__(self, db: Session):
        """
        Initialize the data cleanup service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def cleanup_ping_results(self) -> int:
        """
        Clean up old ping results, keeping last 100 per VM.
        
        Uses PostgreSQL window functions with ROW_NUMBER() OVER (PARTITION BY vm_id)
        to efficiently identify and delete old records while preserving recent history.
        
        Returns:
            Number of records deleted
            
        Requirements: 4.6 - Maintain history of last 100 Custom_Ping results per VM
        """
        logger.info("Starting ping results cleanup")
        
        try:
            # Use window function to identify records beyond retention limit
            # ROW_NUMBER() assigns sequential numbers within each VM partition
            # ordered by timestamp descending (newest first)
            query = text("""
                DELETE FROM ping_results
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY vm_id ORDER BY timestamp DESC
                        ) as rn
                        FROM ping_results
                    ) t WHERE rn > :retention_limit
                )
            """)
            
            result = self.db.execute(query, {'retention_limit': self.PING_RESULTS_RETENTION})
            deleted_count = result.rowcount
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old ping results (retention: {self.PING_RESULTS_RETENTION} per VM)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup ping results: {e}")
            self.db.rollback()
            raise DataCleanupServiceError(f"Failed to cleanup ping results: {e}")
    
    def cleanup_metrics(self) -> int:
        """
        Clean up old metrics, keeping last 1000 per VM.
        
        Uses PostgreSQL window functions with ROW_NUMBER() OVER (PARTITION BY vm_id)
        to efficiently identify and delete old records while preserving recent history.
        
        Returns:
            Number of records deleted
            
        Requirements: 5.7 - Store most recent 1000 metric data points per VM
        """
        logger.info("Starting metrics cleanup")
        
        try:
            # Use window function to identify records beyond retention limit
            # ROW_NUMBER() assigns sequential numbers within each VM partition
            # ordered by timestamp descending (newest first)
            query = text("""
                DELETE FROM metrics
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY vm_id ORDER BY timestamp DESC
                        ) as rn
                        FROM metrics
                    ) t WHERE rn > :retention_limit
                )
            """)
            
            result = self.db.execute(query, {'retention_limit': self.METRICS_RETENTION})
            deleted_count = result.rowcount
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old metrics (retention: {self.METRICS_RETENTION} per VM)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup metrics: {e}")
            self.db.rollback()
            raise DataCleanupServiceError(f"Failed to cleanup metrics: {e}")
    
    def cleanup_alerts(self) -> int:
        """
        Clean up old alerts, retaining for 90 days.
        
        Deletes alerts older than 90 days based on sent_at timestamp.
        
        Returns:
            Number of records deleted
            
        Requirements: 4.6, 5.7 - Data retention policies
        """
        logger.info("Starting alerts cleanup")
        
        try:
            # Calculate cutoff date (90 days ago)
            cutoff_date = datetime.utcnow() - timedelta(days=self.ALERTS_RETENTION_DAYS)
            
            # Delete alerts older than cutoff date
            query = text("""
                DELETE FROM alerts
                WHERE sent_at < :cutoff_date
            """)
            
            result = self.db.execute(query, {'cutoff_date': cutoff_date})
            deleted_count = result.rowcount
            self.db.commit()
            
            logger.info(
                f"Cleaned up {deleted_count} old alerts "
                f"(retention: {self.ALERTS_RETENTION_DAYS} days, cutoff: {cutoff_date.isoformat()})"
            )
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup alerts: {e}")
            self.db.rollback()
            raise DataCleanupServiceError(f"Failed to cleanup alerts: {e}")
    
    def cleanup_all(self) -> CleanupStats:
        """
        Execute all cleanup operations and return statistics.
        
        This method is designed to be called by the scheduled Celery task
        that runs daily at 2 AM.
        
        Returns:
            CleanupStats with counts of deleted records
            
        Requirements: 4.6, 5.7 - Data retention policies
        """
        logger.info("Starting full data cleanup cycle")
        start_time = datetime.utcnow()
        
        stats = CleanupStats()
        
        try:
            # Cleanup ping results
            stats.ping_results_deleted = self.cleanup_ping_results()
            
            # Cleanup metrics
            stats.metrics_deleted = self.cleanup_metrics()
            
            # Cleanup alerts
            stats.alerts_deleted = self.cleanup_alerts()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed full data cleanup cycle in {elapsed:.2f}s: "
                f"ping_results={stats.ping_results_deleted}, "
                f"metrics={stats.metrics_deleted}, "
                f"alerts={stats.alerts_deleted}"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Data cleanup cycle failed: {e}")
            raise DataCleanupServiceError(f"Data cleanup cycle failed: {e}")
