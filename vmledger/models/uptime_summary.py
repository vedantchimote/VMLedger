"""
Uptime summary model for daily rollup of ping results.
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from vmledger.database import Base


class UptimeDailySummary(Base):
    """
    Daily rollup of ping results for SLA calculations.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table
        date: The date this summary represents
        total_checks: Total number of ping checks that day
        successful_checks: Number of successful checks
        avg_latency_ms: Average response time
        max_latency_ms: Maximum response time
        min_latency_ms: Minimum response time
    """
    __tablename__ = "uptime_daily_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    total_checks = Column(Integer, nullable=False, default=0)
    successful_checks = Column(Integer, nullable=False, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    max_latency_ms = Column(Float, nullable=True)
    min_latency_ms = Column(Float, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('vm_id', 'date', name='unique_vm_daily_summary'),
    )
    
    vm = relationship("VM")
    
    def __repr__(self):
        return f"<UptimeDailySummary(vm_id={self.vm_id}, date={self.date}, total={self.total_checks}, success={self.successful_checks})>"
