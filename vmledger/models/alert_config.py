"""
AlertConfig model for alert configuration per VM.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
from vmledger.database import Base


class AlertConfig(Base):
    """
    AlertConfig model for configuring alert notifications per VM.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table
        enabled: Whether alerts are enabled for this VM
        webhook_url: Webhook URL for notifications
        email_recipient: Email address for notifications
        cooldown_minutes: Cooldown period between alerts (default 15)
        created_at: Timestamp of config creation
        updated_at: Timestamp of last update
        
    Relationships:
        vm: The VM this alert config belongs to
    """
    __tablename__ = "alert_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    webhook_url = Column(Text, nullable=True)
    email_recipient = Column(String(255), nullable=True)
    cooldown_minutes = Column(Integer, default=15, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "webhook_url IS NOT NULL OR email_recipient IS NOT NULL",
            name='at_least_one_method'
        ),
    )
    
    # Relationships
    vm = relationship("VM", back_populates="alert_config")
    
    def __repr__(self):
        return f"<AlertConfig(id={self.id}, vm_id={self.vm_id}, enabled={self.enabled})>"
