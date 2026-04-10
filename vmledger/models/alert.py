"""
Alert model for alert history.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from vmledger.database import Base


class Alert(Base):
    """
    Alert model for storing alert notification history.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table
        alert_type: Type of alert (e.g., 'VM_UNREACHABLE', 'VM_RECOVERED')
        sent_at: Timestamp when alert was sent
        notification_method: Method used ('webhook' or 'email')
        success: Whether the notification was sent successfully
        error_message: Error message if notification failed
        
    Relationships:
        vm: The VM this alert belongs to
    """
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notification_method = Column(String(20), nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_alerts_sent_at', 'sent_at', postgresql_ops={'sent_at': 'DESC'}),
    )
    
    # Relationships
    vm = relationship("VM", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert(id={self.id}, vm_id={self.vm_id}, type='{self.alert_type}', success={self.success})>"
