"""
VM model for virtual machine registry.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func, Index
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import relationship
from vmledger.database import Base


class VM(Base):
    """
    VM model representing a registered virtual machine.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        ip_address: IPv4 or IPv6 address (max 45 chars for IPv6)
        hostname: VM hostname
        domain: Optional domain name
        ssh_port: SSH port number (default 22)
        tags: Array of string tags
        deployment_notes: Markdown-formatted deployment documentation
        search_vector: Full-text search vector (tsvector)
        created_at: Timestamp of VM registration
        updated_at: Timestamp of last update
        last_seen: Timestamp of last successful ping
        is_reachable: Current reachability status
        
    Relationships:
        user: Owner of this VM
        credentials: SSH credentials for this VM
        ping_results: Ping check history
        metrics: Resource metrics history
        alerts: Alert history
        alert_config: Alert configuration
    """
    __tablename__ = "vms"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # Supports IPv6
    hostname = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    ssh_port = Column(Integer, nullable=False, default=22)
    tags = Column(ARRAY(Text), nullable=True)
    deployment_notes = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    is_reachable = Column(Boolean, nullable=True)
    
    # DNS resolution tracking
    resolved_ip = Column(String(45), nullable=True)  # Last resolved IP from hostname
    dns_last_checked = Column(DateTime(timezone=True), nullable=True)  # When DNS was last checked
    dns_mismatch = Column(Boolean, nullable=True, default=False)  # True if resolved_ip != ip_address
    
    # Custom monitoring intervals
    ping_interval_minutes = Column(Integer, nullable=False, server_default='5', default=5)
    dns_interval_hours = Column(Integer, nullable=False, server_default='6', default=6)
    ping_last_checked = Column(DateTime(timezone=True), nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'ip_address', 'ssh_port', name='unique_vm_per_user'),
        CheckConstraint('ssh_port >= 1 AND ssh_port <= 65535', name='valid_ssh_port'),
        Index('idx_vms_search', 'search_vector', postgresql_using='gin'),
        Index('idx_vms_tags', 'tags', postgresql_using='gin'),
    )
    
    # Relationships
    user = relationship("User", back_populates="vms")
    credentials = relationship("Credential", back_populates="vm", uselist=False, cascade="all, delete-orphan")
    ping_results = relationship("PingResult", back_populates="vm", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="vm", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="vm", cascade="all, delete-orphan")
    alert_config = relationship("AlertConfig", back_populates="vm", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<VM(id={self.id}, hostname='{self.hostname}', ip='{self.ip_address}', port={self.ssh_port})>"
