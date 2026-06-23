"""
Process Manager API for LXC containers via SSH.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Path
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from vmledger.database import get_db
from vmledger.api.lxc import _get_ssh_client, _detect_lxc_provider
from vmledger.services.ssh_utils import SSHUtils

logger = logging.getLogger(__name__)

router = APIRouter()

class ProcessInfo(BaseModel):
    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    vsz_kb: int
    rss_kb: int
    stat: str
    started: str
    time: str
    command: str

class ProcessListResponse(BaseModel):
    container_id: str
    process_count: int
    processes: List[ProcessInfo]

class KillProcessRequest(BaseModel):
    signal: str = "TERM"

    @validator('signal')
    def validate_signal(cls, v):
        allowed = {"TERM", "KILL", "HUP", "INT"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Signal must be one of {allowed}")
        return v

def get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)

@router.get("/{vm_id}/lxc/{lxc_id}/processes", response_model=ProcessListResponse)
def list_container_processes(
    vm_id: int,
    lxc_id: str = Path(..., regex="^[a-zA-Z0-9_-]+$"),
    sort: str = Query("cpu", description="Sort by cpu, mem, or pid"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get top processes running inside an LXC container."""
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        
        sort_map = {"cpu": "-%cpu", "mem": "-%mem", "pid": "pid"}
        sort_flag = sort_map.get(sort.lower(), "-%cpu")
        
        # Build command depending on provider
        if provider == "pct":
            cmd = f"pct exec {lxc_id} -- ps aux --sort={sort_flag}"
        elif provider == "lxd":
            cmd = f"lxc exec {lxc_id} -- ps aux --sort={sort_flag}"
        else:
            # lxc-utils
            cmd = f"lxc-attach -n {lxc_id} -- ps aux --sort={sort_flag}"
            
        stdout, stderr, exit_code = SSHUtils.execute_command(client, cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to fetch processes: {stderr}")
            
        lines = stdout.strip().split('\n')
        if not lines or len(lines) < 2:
            return ProcessListResponse(container_id=lxc_id, process_count=0, processes=[])
            
        # Parse ps aux output (skip header)
        processes = []
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
                
            try:
                processes.append(ProcessInfo(
                    user=parts[0],
                    pid=int(parts[1]),
                    cpu_percent=float(parts[2]),
                    mem_percent=float(parts[3]),
                    vsz_kb=int(parts[4]),
                    rss_kb=int(parts[5]),
                    stat=parts[7],
                    started=parts[8],
                    time=parts[9],
                    command=parts[10].strip()
                ))
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse ps output line: {line}. Error: {e}")
                continue
                
        return ProcessListResponse(
            container_id=lxc_id,
            process_count=len(processes),
            processes=processes[:limit]
        )
    finally:
        client.close()

@router.post("/{vm_id}/lxc/{lxc_id}/processes/{pid}/kill")
def kill_container_process(
    vm_id: int,
    pid: int,
    request_data: KillProcessRequest,
    lxc_id: str = Path(..., regex="^[a-zA-Z0-9_-]+$"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Kill a specific process inside a container."""
    if pid <= 1:
        raise HTTPException(status_code=400, detail="Cannot kill PID 1 or 0 (init process)")
        
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        signal = request_data.signal
        
        if provider == "pct":
            cmd = f"pct exec {lxc_id} -- kill -{signal} {pid}"
        elif provider == "lxd":
            cmd = f"lxc exec {lxc_id} -- kill -{signal} {pid}"
        else:
            cmd = f"lxc-attach -n {lxc_id} -- kill -{signal} {pid}"
            
        stdout, stderr, exit_code = SSHUtils.execute_command(client, cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to kill process {pid}: {stderr}")
            
        return {"success": True, "message": f"Sent {signal} to PID {pid}"}
    finally:
        client.close()
