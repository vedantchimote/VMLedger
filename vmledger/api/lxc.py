"""
LXC Container Management API endpoints.
"""

import logging
import re
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Path

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

class LxcResources(BaseModel):
    cpu_cores: int | None = None
    memory_mb: int | None = None
    swap_mb: int | None = None
    disk_gb: float | None = None
    disk_used_gb: float | None = None

class LxcResourcesResponse(BaseModel):
    container_id: str
    provider: str
    resources: LxcResources
    raw_config: str

class UpdateLxcResourcesRequest(BaseModel):
    cpu_cores: int | None = None
    memory_mb: int | None = None
    swap_mb: int | None = None
    disk_gb: float | None = None


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

@router.get("/{vm_id}/lxc/{lxc_id}/resources", response_model=LxcResourcesResponse)
def get_lxc_resources(
    vm_id: int,
    lxc_id: str = Path(..., regex=r"^[a-zA-Z0-9_-]+$"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get container resource limits and live usage."""
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        if provider == "none":
            raise HTTPException(status_code=400, detail="LXC provider not found")
        
        resources = LxcResources()
        raw_config = ""
        
        # Build exec prefix for running commands inside the container
        if provider == "pct":
            exec_prefix = f"pct exec {lxc_id} --"
        elif provider == "lxd":
            exec_prefix = f"lxc exec {lxc_id} --"
        else:
            exec_prefix = f"lxc-attach -n {lxc_id} --"
        
        # --- Get config for raw display ---
        if provider == "pct":
            config_cmd = f"pct config {lxc_id}"
        elif provider == "lxd":
            config_cmd = f"lxc config show {lxc_id}"
        else:
            config_cmd = f"cat /var/lib/lxc/{lxc_id}/config 2>/dev/null || echo 'Config not available'"
        
        config_stdout, _, config_exit = SSHUtils.execute_command(client, config_cmd)
        if config_exit == 0:
            raw_config = config_stdout
        
        # --- Parse configured limits from config ---
        if provider == "pct":
            for line in raw_config.split('\n'):
                line = line.strip()
                if line.startswith('cores:'):
                    try: resources.cpu_cores = int(line.split(':',1)[1].strip())
                    except: pass
                elif line.startswith('memory:'):
                    try: resources.memory_mb = int(line.split(':',1)[1].strip())
                    except: pass
                elif line.startswith('swap:'):
                    try: resources.swap_mb = int(line.split(':',1)[1].strip())
                    except: pass
                elif line.startswith('rootfs:'):
                    try:
                        size_str = line.split('size=')[1].strip().rstrip(',')
                        if size_str.upper().endswith('G'):
                            resources.disk_gb = float(size_str[:-1])
                        elif size_str.upper().endswith('M'):
                            resources.disk_gb = float(size_str[:-1]) / 1024
                        elif size_str.upper().endswith('T'):
                            resources.disk_gb = float(size_str[:-1]) * 1024
                    except: pass
                    
        elif provider == "lxd":
            # LXD config is YAML. Parse limits from nested config section.
            for line in raw_config.split('\n'):
                line = line.strip()
                if line.startswith('limits.cpu:'):
                    try: 
                        val = line.split(':', 1)[1].strip().strip('"').strip("'")
                        resources.cpu_cores = int(val)
                    except: pass
                elif line.startswith('limits.memory:'):
                    try:
                        mem_str = line.split(':', 1)[1].strip().strip('"').strip("'")
                        if mem_str.upper().endswith('MB'):
                            resources.memory_mb = int(mem_str[:-2])
                        elif mem_str.upper().endswith('GB'):
                            resources.memory_mb = int(float(mem_str[:-2]) * 1024)
                        elif mem_str.upper().endswith('MIB'):
                            resources.memory_mb = int(mem_str[:-3])
                        elif mem_str.upper().endswith('GIB'):
                            resources.memory_mb = int(float(mem_str[:-3]) * 1024)
                        else:
                            # Assume bytes
                            resources.memory_mb = int(mem_str) // (1024 * 1024)
                    except: pass
        
        # --- Fallback: query live values from inside the container ---
        # CPU cores
        if resources.cpu_cores is None:
            stdout, _, exit_code = SSHUtils.execute_command(client, f"{exec_prefix} nproc 2>/dev/null || {exec_prefix} grep -c ^processor /proc/cpuinfo")
            if exit_code == 0 and stdout.strip():
                try: resources.cpu_cores = int(stdout.strip().split('\n')[-1])
                except: pass
        
        # Memory
        if resources.memory_mb is None:
            stdout, _, exit_code = SSHUtils.execute_command(client, f"{exec_prefix} free -m")
            if exit_code == 0 and stdout.strip():
                for line in stdout.strip().split('\n'):
                    if line.lower().startswith('mem:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            try: resources.memory_mb = int(parts[1])
                            except: pass
                            break
        
        # Swap
        if resources.swap_mb is None:
            stdout, _, exit_code = SSHUtils.execute_command(client, f"{exec_prefix} free -m")
            if exit_code == 0 and stdout.strip():
                for line in stdout.strip().split('\n'):
                    if line.lower().startswith('swap:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            try: resources.swap_mb = int(parts[1])
                            except: pass
                            break
        
        # Disk
        if resources.disk_gb is None:
            stdout, _, exit_code = SSHUtils.execute_command(client, f"{exec_prefix} df -BG / 2>/dev/null | tail -1")
            if exit_code == 0 and stdout.strip():
                parts = stdout.strip().split()
                if len(parts) >= 2:
                    try:
                        size_str = parts[1].rstrip('G')
                        resources.disk_gb = float(size_str)
                    except: pass
            # Also try to get used disk
            stdout2, _, exit_code2 = SSHUtils.execute_command(client, f"{exec_prefix} df -BG / 2>/dev/null | tail -1")
            if exit_code2 == 0 and stdout2.strip():
                parts2 = stdout2.strip().split()
                if len(parts2) >= 3:
                    try:
                        used_str = parts2[2].rstrip('G')
                        resources.disk_used_gb = float(used_str)
                    except: pass
        
        return LxcResourcesResponse(
            container_id=lxc_id,
            provider=provider,
            resources=resources,
            raw_config=raw_config
        )
    finally:
        client.close()

@router.put("/{vm_id}/lxc/{lxc_id}/resources")
def update_lxc_resources(
    vm_id: int,
    request_data: UpdateLxcResourcesRequest,
    lxc_id: str = Path(..., regex=r"^[a-zA-Z0-9_-]+$"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Update container resource limits."""
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        if provider == "none":
            raise HTTPException(status_code=400, detail="LXC provider not found")
        if provider == "lxc-utils":
            raise HTTPException(status_code=400, detail="Editing limits not supported for pure LXC via this API")
            
        cmds = []
        if provider == "pct":
            if request_data.cpu_cores is not None:
                cmds.append(f"pct set {lxc_id} -cores {request_data.cpu_cores}")
            if request_data.memory_mb is not None:
                cmds.append(f"pct set {lxc_id} -memory {request_data.memory_mb}")
            if request_data.swap_mb is not None:
                cmds.append(f"pct set {lxc_id} -swap {request_data.swap_mb}")
            if request_data.disk_gb is not None:
                # pct resize {id} rootfs +5G or absolute? pct resize {id} rootfs {size}G
                cmds.append(f"pct resize {lxc_id} rootfs {request_data.disk_gb}G")
                
        elif provider == "lxd":
            if request_data.cpu_cores is not None:
                cmds.append(f"lxc config set {lxc_id} limits.cpu {request_data.cpu_cores}")
            if request_data.memory_mb is not None:
                cmds.append(f"lxc config set {lxc_id} limits.memory {request_data.memory_mb}MB")
            if request_data.disk_gb is not None:
                cmds.append(f"lxc config device set {lxc_id} root size {request_data.disk_gb}GB")
                
        if not cmds:
            return {"success": True, "message": "No changes requested"}
            
        full_cmd = " && ".join(cmds)
        stdout, stderr, exit_code = SSHUtils.execute_command(client, full_cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to apply limits: {stderr or stdout}")
            
        return {"success": True, "message": "Resources updated successfully"}
    finally:
        client.close()

