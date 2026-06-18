"""
Service Health Monitor API endpoints.
"""

import logging
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from vmledger.database import get_db
from vmledger.models.vm import VM
from vmledger.models.service_check import ServiceConfig, ServiceStatus
from vmledger.services.metric_collector_service import MetricCollectorService

logger = logging.getLogger(__name__)

router = APIRouter()

# Schemas
class ServiceConfigCreate(BaseModel):
    service_name: str
    display_name: str | None = None
    check_command: str | None = None

class ServiceStatusResponse(BaseModel):
    id: int
    vm_id: int
    service_name: str
    display_name: str | None
    check_command: str | None
    enabled: bool
    status: str | None
    
    class Config:
        from_attributes = True


def get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)


@router.get("/{vm_id}/services", response_model=List[ServiceStatusResponse])
def get_vm_services(
    vm_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get all configured services and their latest status for a VM."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    configs = db.query(ServiceConfig).filter(ServiceConfig.vm_id == vm_id).all()
    statuses = {s.service_name: s.status for s in db.query(ServiceStatus).filter(ServiceStatus.vm_id == vm_id).all()}
    
    result = []
    for conf in configs:
        result.append(ServiceStatusResponse(
            id=conf.id,
            vm_id=conf.vm_id,
            service_name=conf.service_name,
            display_name=conf.display_name,
            check_command=conf.check_command,
            enabled=conf.enabled,
            status=statuses.get(conf.service_name)
        ))
        
    return result


@router.post("/{vm_id}/services", response_model=ServiceStatusResponse)
def add_vm_service(
    vm_id: int,
    data: ServiceConfigCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Add a service to monitor for a VM."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    # Check if already exists
    existing = db.query(ServiceConfig).filter(
        ServiceConfig.vm_id == vm_id, 
        ServiceConfig.service_name == data.service_name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Service already configured for this VM")
        
    new_config = ServiceConfig(
        vm_id=vm_id,
        service_name=data.service_name,
        display_name=data.display_name,
        check_command=data.check_command
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return ServiceStatusResponse(
        id=new_config.id,
        vm_id=new_config.vm_id,
        service_name=new_config.service_name,
        display_name=new_config.display_name,
        check_command=new_config.check_command,
        enabled=new_config.enabled,
        status="unknown"
    )


@router.delete("/{vm_id}/services/{service_id}")
def delete_vm_service(
    vm_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Remove a service from monitoring."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    config = db.query(ServiceConfig).filter(
        ServiceConfig.id == service_id,
        ServiceConfig.vm_id == vm_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Service configuration not found")
        
    # Clean up status as well
    db.query(ServiceStatus).filter(
        ServiceStatus.vm_id == vm_id,
        ServiceStatus.service_name == config.service_name
    ).delete()
    
    db.delete(config)
    db.commit()
    
    return {"success": True}


@router.post("/{vm_id}/services/check")
def check_vm_services(
    vm_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Trigger an on-demand check for all configured services."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    configs = db.query(ServiceConfig).filter(
        ServiceConfig.vm_id == vm_id,
        ServiceConfig.enabled == True
    ).all()
    
    if not configs:
        return {"success": True, "message": "No services configured"}
        
    # Trigger metric collection via Celery to avoid blocking
    from vmledger.tasks import collect_metrics_task
    collect_metrics_task.delay(vm_id)
    
    return {"success": True, "message": "Service check triggered"}
