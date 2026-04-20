"""
Pydantic schemas for VM-related API requests and responses.

These schemas provide input validation and serialization for VM operations.
"""

from pydantic import BaseModel, Field, field_validator, IPvAnyAddress
from typing import List, Optional
from datetime import datetime
import ipaddress


class VMCreateSchema(BaseModel):
    """
    Schema for creating a new VM.
    
    Validates:
    - IP address format (IPv4 or IPv6)
    - SSH port range (1-65535)
    - Hostname length (1-255 characters)
    - Tags limit (max 20 tags)
    - Deployment notes length (max 50,000 characters)
    - At least one credential type (SSH key or password)
    
    Requirements: 1.1-1.6, 2.1-2.5, 6.4
    """
    ip_address: str = Field(..., description="IPv4 or IPv6 address")
    hostname: str = Field(..., min_length=1, max_length=255, description="VM hostname")
    domain: Optional[str] = Field(None, max_length=255, description="Domain name")
    ssh_port: int = Field(default=22, ge=1, le=65535, description="SSH port number")
    tags: List[str] = Field(default_factory=list, max_length=20, description="List of tags (max 20)")
    deployment_notes: Optional[str] = Field(None, max_length=50000, description="Markdown deployment notes")
    
    # Credentials (one of these required)
    ssh_username: str = Field(default="root", description="SSH username")
    ssh_private_key: Optional[str] = Field(None, description="SSH private key (PEM format)")
    ssh_password: Optional[str] = Field(None, description="SSH password")
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        """
        Validate IP address format (IPv4 or IPv6).
        
        Requirements: 1.2
        """
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """
        Validate tags list (max 20 tags).
        
        Requirements: 1.4
        """
        if len(v) > 20:
            raise ValueError(f"Maximum 20 tags allowed, got {len(v)}")
        return v
    
    def model_post_init(self, __context) -> None:
        """
        Validate that at least one credential type is provided.
        
        Requirements: 2.1, 2.2
        """
        if not self.ssh_private_key and not self.ssh_password:
            raise ValueError("Either ssh_private_key or ssh_password must be provided")


class VMUpdateSchema(BaseModel):
    """
    Schema for updating an existing VM.
    
    All fields are optional to support partial updates.
    
    Requirements: 11.1
    """
    ip_address: Optional[str] = Field(None, description="IPv4 or IPv6 address")
    hostname: Optional[str] = Field(None, min_length=1, max_length=255, description="VM hostname")
    domain: Optional[str] = Field(None, max_length=255, description="Domain name")
    ssh_port: Optional[int] = Field(None, ge=1, le=65535, description="SSH port number")
    tags: Optional[List[str]] = Field(None, max_length=20, description="List of tags (max 20)")
    deployment_notes: Optional[str] = Field(None, max_length=50000, description="Markdown deployment notes")
    ssh_username: Optional[str] = Field(None, description="SSH username")
    ssh_private_key: Optional[str] = Field(None, description="SSH private key (PEM format)")
    ssh_password: Optional[str] = Field(None, description="SSH password")
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate IP address format if provided."""
        if v is not None:
            try:
                ipaddress.ip_address(v)
                return v
            except ValueError:
                raise ValueError(f"Invalid IP address format: {v}")
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags list if provided."""
        if v is not None and len(v) > 20:
            raise ValueError(f"Maximum 20 tags allowed, got {len(v)}")
        return v


class VMResponseSchema(BaseModel):
    """
    Schema for VM response data.
    
    Includes VM metadata and latest monitoring data.
    
    Requirements: 12.1-12.6
    """
    id: int
    ip_address: str
    hostname: str
    domain: Optional[str]
    ssh_port: int
    tags: List[str]
    deployment_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_seen: Optional[datetime]
    is_reachable: Optional[bool]
    
    # Latest metrics (can be joined from metrics table)
    latest_cpu: Optional[float] = None
    latest_ram_used: Optional[int] = None
    latest_ram_total: Optional[int] = None
    latest_disk_percent: Optional[float] = None
    
    model_config = {
        "from_attributes": True
    }


class VMListResponseSchema(BaseModel):
    """
    Schema for paginated VM list response.
    """
    vms: List[VMResponseSchema]
    total: int
    page: int
    per_page: int
    pages: int


class VMFilters(BaseModel):
    """
    Schema for VM list filtering and pagination.
    """
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=100, description="Items per page")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    is_reachable: Optional[bool] = Field(None, description="Filter by reachability status")
