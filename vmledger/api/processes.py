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


def _build_exec_prefix(provider: str, lxc_id: str) -> str:
    """Build the container exec command prefix based on provider."""
    if provider == "pct":
        return f"pct exec {lxc_id} --"
    elif provider == "lxd":
        return f"lxc exec {lxc_id} --"
    else:
        return f"lxc-attach -n {lxc_id} --"


def _parse_ps_output(stdout: str) -> List[dict]:
    """
    Parse `ps aux` output into structured process records.
    
    `ps aux` columns: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
    """
    lines = stdout.strip().split('\n')
    if not lines or len(lines) < 2:
        return []
    
    processes = []
    for line in lines[1:]:  # skip header
        parts = line.split(None, 10)
        if len(parts) < 11:
            # Try a lenient parse for shorter output
            if len(parts) >= 4:
                try:
                    processes.append({
                        "user": parts[0],
                        "pid": int(parts[1]),
                        "cpu_percent": float(parts[2]) if len(parts) > 2 else 0.0,
                        "mem_percent": float(parts[3]) if len(parts) > 3 else 0.0,
                        "vsz_kb": int(parts[4]) if len(parts) > 4 else 0,
                        "rss_kb": int(parts[5]) if len(parts) > 5 else 0,
                        "stat": parts[7] if len(parts) > 7 else "?",
                        "started": parts[8] if len(parts) > 8 else "?",
                        "time": parts[9] if len(parts) > 9 else "0:00",
                        "command": parts[-1].strip(),
                    })
                except (ValueError, IndexError):
                    continue
            continue

        try:
            processes.append({
                "user": parts[0],
                "pid": int(parts[1]),
                "cpu_percent": float(parts[2]),
                "mem_percent": float(parts[3]),
                "vsz_kb": int(parts[4]),
                "rss_kb": int(parts[5]),
                "stat": parts[7],
                "started": parts[8],
                "time": parts[9],
                "command": parts[10].strip(),
            })
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse ps output line: {line}. Error: {e}")
            continue
    
    return processes


def _parse_top_output(stdout: str) -> dict:
    """
    Parse `top -bn1` output to extract per-PID real-time CPU usage.
    Returns a dict: {pid: cpu_percent}.
    """
    cpu_map = {}
    lines = stdout.strip().split('\n')
    header_found = False
    pid_col = None
    cpu_col = None
    
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        
        # Find the header line to determine column positions
        if not header_found:
            upper_parts = [p.upper() for p in parts]
            if 'PID' in upper_parts and '%CPU' in upper_parts:
                pid_col = upper_parts.index('PID')
                cpu_col = upper_parts.index('%CPU')
                header_found = True
            continue
        
        # Parse data lines
        if pid_col is not None and cpu_col is not None and len(parts) > max(pid_col, cpu_col):
            try:
                pid = int(parts[pid_col])
                cpu = float(parts[cpu_col])
                cpu_map[pid] = cpu
            except (ValueError, IndexError):
                continue
    
    return cpu_map


@router.get("/{vm_id}/lxc/{lxc_id}/processes", response_model=ProcessListResponse)
def list_container_processes(
    vm_id: int,
    lxc_id: str = Path(..., regex="^[a-zA-Z0-9_-]+$"),
    sort: str = Query("cpu", description="Sort by cpu, mem, or pid"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id)
):
    """Get top processes running inside an LXC container with real-time CPU."""
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        prefix = _build_exec_prefix(provider, lxc_id)
        
        # Step 1: Get process list via ps aux
        ps_cmd = f"{prefix} ps aux"
        stdout, stderr, exit_code = SSHUtils.execute_command(client, ps_cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to fetch processes: {stderr}")
        
        processes = _parse_ps_output(stdout)
        
        if not processes:
            return ProcessListResponse(container_id=lxc_id, process_count=0, processes=[])
        
        # Step 2: Get real-time CPU from top -bn1
        top_cmd = f"{prefix} top -bn1 -d0.5"
        top_stdout, top_stderr, top_exit = SSHUtils.execute_command(client, top_cmd, command_timeout=10)
        
        if top_exit == 0 and top_stdout.strip():
            cpu_map = _parse_top_output(top_stdout)
            # Merge real-time CPU values into ps data
            for proc in processes:
                if proc["pid"] in cpu_map:
                    proc["cpu_percent"] = cpu_map[proc["pid"]]
        else:
            logger.debug(f"top command failed for container {lxc_id}, using ps aux CPU values")
        
        # Step 3: Sort
        sort_key = {
            "cpu": lambda p: p["cpu_percent"],
            "mem": lambda p: p["mem_percent"],
            "pid": lambda p: p["pid"],
        }.get(sort.lower(), lambda p: p["cpu_percent"])
        
        reverse = sort.lower() != "pid"
        processes.sort(key=sort_key, reverse=reverse)
        
        # Step 4: Convert to response models
        result = []
        for p in processes[:limit]:
            result.append(ProcessInfo(
                pid=p["pid"],
                user=p["user"],
                cpu_percent=p["cpu_percent"],
                mem_percent=p["mem_percent"],
                vsz_kb=p["vsz_kb"],
                rss_kb=p["rss_kb"],
                stat=p["stat"],
                started=p["started"],
                time=p["time"],
                command=p["command"],
            ))
        
        return ProcessListResponse(
            container_id=lxc_id,
            process_count=len(result),
            processes=result
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
        prefix = _build_exec_prefix(provider, lxc_id)
        signal = request_data.signal
        
        cmd = f"{prefix} kill -{signal} {pid}"
        stdout, stderr, exit_code = SSHUtils.execute_command(client, cmd)
        
        if exit_code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to kill process {pid}: {stderr}")
            
        return {"success": True, "message": f"Sent {signal} to PID {pid}"}
    finally:
        client.close()
