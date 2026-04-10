"""
Credential model for encrypted SSH credentials storage.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
from vmledger.database import Base


class Credential(Base):
    """
    Credential model for storing encrypted SSH credentials.
    
    Attributes:
        id: Primary key
        vm_id: Foreign key to vms table (unique - one credential per VM)
        auth_type: Authentication type ('ssh_key' or 'password')
        encrypted_credential: AES-256 encrypted credential data
        ssh_username: SSH username (default 'root')
        created_at: Timestamp of credential creation
        updated_at: Timestamp of last update
        
    Relationships:
        vm: The VM this credential belongs to
    """
    __tablename__ = "credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    auth_type = Column(String(20), nullable=False)
    encrypted_credential = Column(Text, nullable=False)
    ssh_username = Column(String(100), nullable=False, default='root')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("auth_type IN ('ssh_key', 'password')", name='valid_auth_type'),
    )
    
    # Relationships
    vm = relationship("VM", back_populates="credentials")
    
    def __repr__(self):
        return f"<Credential(id={self.id}, vm_id={self.vm_id}, auth_type='{self.auth_type}', username='{self.ssh_username}')>"
