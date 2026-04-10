"""
Metric model for resource usage data.
"""

from sqlalchemy import Column, Integer, Float, Text, Boolean, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from vmledger.database import Base


class Metric(Base):
    """
    Metric model for storing VM resource usage metrics.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table
        timestamp: Timestamp of metric collection
        cpu_usage_percent: CPU usage percentage
        ram_used_mb: RAM used in megabytes
        ram_total_mb: Total RAM in megabytes
        disk_used_gb: Disk used in gigabytes
        disk_total_gb: Total disk in gigabytes
        disk_usage_percent: Disk usage percentage
        collection_success: Whether metric collection succeeded
        error_message: Error message if collection failed
        
    Relationships:
        vm: The VM this metric belongs to
    """
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    cpu_usage_percent = Column(Float, nullable=True)
    ram_used_mb = Column(Integer, nullable=True)
    ram_total_mb = Column(Integer, nullable=True)
    disk_used_gb = Column(Float, nullable=True)
    disk_total_gb = Column(Float, nullable=True)
    disk_usage_percent = Column(Float, nullable=True)
    collection_success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_timestamp', 'timestamp', postgresql_ops={'timestamp': 'DESC'}),
        Index('idx_metrics_vm_timestamp', 'vm_id', 'timestamp', postgresql_ops={'timestamp': 'DESC'}),
    )
    
    # Relationships
    vm = relationship("VM", back_populates="metrics")
    
    def __repr__(self):
        return f"<Metric(id={self.id}, vm_id={self.vm_id}, cpu={self.cpu_usage_percent}%, timestamp={self.timestamp})>"
