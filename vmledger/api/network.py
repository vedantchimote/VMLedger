"""
Network Topology API for LXC containers via SSH.
"""

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from vmledger.database import get_db
from vmledger.api.lxc import _get_ssh_client, _detect_lxc_provider, get_user_id
from vmledger.services.ssh_utils import SSHUtils

router = APIRouter()

class TopologyNode(BaseModel):
    id: str
    type: str  # 'host', 'bridge', 'container'
    label: str
    ip: str = ""
    status: str = "running"

class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""

class TopologyResponse(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]

@router.get("/{vm_id}/network/topology", response_model=TopologyResponse)
def get_network_topology(vm_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_user_id)):
    """Generate a network topology map of the host and its LXC containers."""
    client = _get_ssh_client(db, vm_id, user_id)
    try:
        provider = _detect_lxc_provider(client)
        
        nodes = []
        edges = []
        
        # Add Host Node
        nodes.append(TopologyNode(id="host", type="host", label="Host VM", ip=""))
        
        # Determine bridges
        stdout, stderr, exit_code = SSHUtils.execute_command(client, "ip -br link show type bridge")
        bridges = set()
        if exit_code == 0:
            for line in stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    bridge_name = parts[0]
                    bridges.add(bridge_name)
                    nodes.append(TopologyNode(id=f"br_{bridge_name}", type="bridge", label=bridge_name))
                    edges.append(TopologyEdge(id=f"host_br_{bridge_name}", source="host", target=f"br_{bridge_name}"))
        
        if not bridges:
            # Fallback if command fails or no bridges
            bridges.add("vmbr0")
            nodes.append(TopologyNode(id="br_vmbr0", type="bridge", label="vmbr0"))
            edges.append(TopologyEdge(id="host_br_vmbr0", source="host", target="br_vmbr0"))

        # Fetch containers and their IPs
        if provider == "pct":
            # Bundle command to prevent SSH channel overhead
            pct_script = '''
            pct list | awk 'NR>1' | while read -r id status name rest; do
                bridge=$(grep -oP '(?<=bridge=)[^,]+' /etc/pve/lxc/$id.conf 2>/dev/null | head -n 1)
                [ -z "$bridge" ] && bridge="vmbr0"
                ip=""
                if [ "$status" = "running" ]; then
                    ip=$(lxc-info -n $id -iH 2>/dev/null | head -n 1)
                fi
                echo "$id|$status|$name|$bridge|$ip"
            done
            '''
            out, stderr, exit_code = SSHUtils.execute_command(client, pct_script)
            if exit_code == 0:
                for line in out.strip().split('\n'):
                    if not line: continue
                    parts = line.split('|')
                    if len(parts) >= 4:
                        c_id, c_status, c_name, c_bridge = parts[0], parts[1], parts[2], parts[3]
                        c_ip = parts[4] if len(parts) > 4 else ""
                        
                        nodes.append(TopologyNode(id=f"lxc_{c_id}", type="container", label=c_name, ip=c_ip, status=c_status))
                        
                        if c_bridge not in bridges:
                            bridges.add(c_bridge)
                            nodes.append(TopologyNode(id=f"br_{c_bridge}", type="bridge", label=c_bridge))
                            edges.append(TopologyEdge(id=f"host_br_{c_bridge}", source="host", target=f"br_{c_bridge}"))

                        edges.append(TopologyEdge(id=f"link_{c_id}_{c_bridge}", source=f"br_{c_bridge}", target=f"lxc_{c_id}"))
        
        elif provider == "lxd":
            out, stderr, exit_code = SSHUtils.execute_command(client, "lxc list -c ns4 --format csv")
            if exit_code == 0:
                for line in out.strip().split('\n'):
                    if not line: continue
                    parts = line.split(',')
                    if len(parts) >= 3:
                        c_name = parts[0].strip('"')
                        c_status = parts[1].strip('"').lower()
                        c_ip = parts[2].strip('"').split(' ')[0] if parts[2] else ""
                        
                        nodes.append(TopologyNode(id=f"lxc_{c_name}", type="container", label=c_name, ip=c_ip, status=c_status))
                        edges.append(TopologyEdge(id=f"link_{c_name}", source="br_lxdbr0", target=f"lxc_{c_name}"))
                        
                        if "lxdbr0" not in bridges:
                            bridges.add("lxdbr0")
                            nodes.append(TopologyNode(id="br_lxdbr0", type="bridge", label="lxdbr0"))
                            edges.append(TopologyEdge(id="host_br_lxdbr0", source="host", target="br_lxdbr0"))
                            
        elif provider == "lxc-utils":
            lxc_script = '''
            lxc-ls -f | awk 'NR>1' | while read -r name status rest; do
                bridge=$(grep '^lxc.net.0.link' /var/lib/lxc/$name/config 2>/dev/null | cut -d= -f2 | tr -d ' ')
                [ -z "$bridge" ] && bridge="lxcbr0"
                ip=""
                if [ "$status" = "RUNNING" ]; then
                    ip=$(lxc-info -n $name -i 2>/dev/null | awk '{print $2}' | head -n 1)
                fi
                echo "$name|$status|$bridge|$ip"
            done
            '''
            out, stderr, exit_code = SSHUtils.execute_command(client, lxc_script)
            if exit_code == 0:
                for line in out.strip().split('\n'):
                    if not line: continue
                    parts = line.split('|')
                    if len(parts) >= 3:
                        c_name = parts[0]
                        c_status = parts[1].lower()
                        c_bridge = parts[2]
                        c_ip = parts[3] if len(parts) > 3 else ""
                        
                        nodes.append(TopologyNode(id=f"lxc_{c_name}", type="container", label=c_name, ip=c_ip, status=c_status))
                        
                        if c_bridge not in bridges:
                            bridges.add(c_bridge)
                            nodes.append(TopologyNode(id=f"br_{c_bridge}", type="bridge", label=c_bridge))
                            edges.append(TopologyEdge(id=f"host_br_{c_bridge}", source="host", target=f"br_{c_bridge}"))
                            
                        edges.append(TopologyEdge(id=f"link_{c_name}", source=f"br_{c_bridge}", target=f"lxc_{c_name}"))
                        
        return TopologyResponse(nodes=nodes, edges=edges)
    finally:
        client.close()
