"""
PingResult model for health check history.
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from vmledger.database import Base


class PingResult(Base):
    """
    PingResult model for storing Custom_Ping check results.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table
        timestamp: Timestamp of ping check
        success: Whether the ping check succeeded
        response_time_ms: Response time in milliseconds (NULL if failed)
        error_type: Error type if failed (NULL if success)
        icmp_success: Whether ICMP ping succeeded
        tcp_success: Whether TCP connection succeeded
        
    Relationships:
        vm: The VM this ping result belongs to
    """
    __tablename__ = "ping_results"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    success = Column(Boolean, nullable=False)
    response_time_ms = Column(Float, nullable=True)
    error_type = Column(String(50), nullable=True)
    icmp_success = Column(Boolean, nullable=True)
    tcp_success = Column(Boolean, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_ping_results_timestamp', 'timestamp', postgresql_ops={'timestamp': 'DESC'}),
    )
    
    # Relationships
    vm = relationship("VM", back_populates="ping_results")
    
    def __repr__(self):
        return f"<PingResult(id={self.id}, vm_id={self.vm_id}, success={self.success}, timestamp={self.timestamp})>"
