"""
LXC Container Management API endpoints.
"""

import logging
import re
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from vmledger.database import get_db
from sqlalchemy.orm import Session
from vmledger.models.vm import VM
from vmledger.models.credential import Credential
from vmledger.services.credential_manager import CredentialManager
from vmledger.services.ssh_utils import SSHUtils

logger = logging.getLogger(__name__)

router = APIRouter()

class LxcContainer(BaseModel):
    vmid: str
    status: str
    name: str

class LxcActionRequest(BaseModel):
    action: str  # 'start', 'stop', 'restart'


def get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)


def _get_ssh_client(db: Session, vm_id: int, user_id: int):
    """Helper to connect to VM via SSH."""
    vm = db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
        
    credential = db.query(Credential).filter(Credential.vm_id == vm_id).first()
    if not credential:
        raise HTTPException(status_code=400, detail="No SSH credentials found for this VM")
        
    cred_manager = CredentialManager(db)
    try:
        if credential.auth_type == 'ssh_key':
            decrypted = cred_manager.decrypt_ssh_key(user_id, credential.encrypted_credential)
        else:
            decrypted = cred_manager.decrypt_password(user_id, credential.encrypted_credential)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decrypt credentials: {e}")
        
    try:
        client = SSHUtils.create_ssh_client(
            ip_address=vm.ip_address,
            port=vm.ssh_port,
            username=credential.ssh_username,
            auth_type=credential.auth_type,
            credential=decrypted,
            connection_timeout=5
        )
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SSH Connection failed: {e}")


def _detect_lxc_provider(client) -> str:
    stdout, _, exit_code = SSHUtils.execute_command(client, "command -v pct")
    if exit_code == 0: return "pct"
    
    stdout, _, exit_code = SSHUtils.execute_command(client, "command -v lxc")
    if exit_code == 0: return "lxd"
    
    stdout, _, exit_code = SSHUtils.execute_command(client, "command -v lxc-ls")
    if exit_code == 0: return "lxc-utils"
    
    return "none"


@router.get("/{vm_id}/lxc", response_model=Dict[str, Any])
def list_lxc_containers(
    vm_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """List all LXC containers running on a VM (supports Proxmox pct, LXD, and standard lxc-utils)."""
    client = _get_ssh_client(db, vm_id, user_id)
    
    try:
        provider = _detect_lxc_provider(client)
        if provider == "none":
            return {"is_proxmox": False, "provider": "none", "containers": []}
            
        containers = []
        
        if provider == "pct":
            stdout, stderr, exit_code = SSHUtils.execute_command(client, "pct list")
            if exit_code == 0:
                lines = stdout.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = re.split(r'\s+', line.strip())
                        if len(parts) >= 3:
                            containers.append({
                                "vmid": parts[0],
                                "status": parts[1].lower(),
                                "name": parts[-1]
                            })
                            
        elif provider == "lxd":
            stdout, stderr, exit_code = SSHUtils.execute_command(client, "lxc list -c ns --format csv")
            if exit_code == 0:
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 2:
                            containers.append({
                                "vmid": parts[0],  # using name as ID for LXD
                                "status": parts[1].lower(),
                                "name": parts[0]
                            })
                            
        elif provider == "lxc-utils":
            stdout, stderr, exit_code = SSHUtils.execute_command(client, "lxc-ls -f")
            if exit_code == 0:
                lines = stdout.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = re.split(r'\s+', line.strip())
                        if len(parts) >= 2:
                            containers.append({
                                "vmid": parts[0],
                                "status": parts[1].lower(),
                                "name": parts[0]
                            })
                            
        return {"is_proxmox": True, "provider": provider, "containers": containers}
        
    finally:
        client.close()


@router.post("/{vm_id}/lxc/{lxc_id}/action")
def perform_lxc_action(
    vm_id: int,
    lxc_id: str,
    payload: LxcActionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Perform start, stop, or restart on an LXC container."""
    if payload.action not in ['start', 'stop', 'restart', 'reboot']:
        raise HTTPException(status_code=400, detail="Invalid action. Must be start, stop, or restart.")
        
    if not re.match(r'^[a-zA-Z0-9_-]+$', lxc_id):
        raise HTTPException(status_code=400, detail="Invalid LXC ID or Name format")
        
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        if provider == "none":
            raise HTTPException(status_code=400, detail="LXC provider not found on the host")
            
        cmd = ""
        if provider == "pct":
            action_cmd = "reboot" if payload.action == "restart" else payload.action
            cmd = f"pct {action_cmd} {lxc_id}"
        elif provider == "lxd":
            cmd = f"lxc {payload.action} {lxc_id}"
        elif provider == "lxc-utils":
            if payload.action == "restart":
                cmd = f"lxc-stop -n {lxc_id}; lxc-start -n {lxc_id}"
            else:
                cmd = f"lxc-{payload.action} -n {lxc_id}"
                
        stdout, stderr, exit_code = SSHUtils.execute_command(client, cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Command failed: {stderr or stdout}")
            
        return {"success": True, "message": f"Container {lxc_id} {payload.action}ed successfully."}
        
    finally:
        client.close()
