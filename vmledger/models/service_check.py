"""
Service check models for VM monitoring.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from vmledger.database import Base


class ServiceConfig(Base):
    """Configures which services to monitor for a VM."""
    __tablename__ = "service_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(100), nullable=False)   # e.g., "nginx", "postgresql"
    display_name = Column(String(100), nullable=True)    # e.g., "Nginx Web Server"
    check_command = Column(String(500), nullable=True)   # Custom command override
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    vm = relationship("VM", backref="service_configs")


class ServiceStatus(Base):
    """Stores the latest result of each service health check."""
    __tablename__ = "service_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)          # "active", "inactive", "failed", "unknown"
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    vm = relationship("VM", backref="service_statuses")
