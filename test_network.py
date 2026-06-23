import sys
from vmledger.database import SessionLocal
from vmledger.api.network import get_network_topology

db = SessionLocal()

print("Testing topology for VM 5...")
try:
    res = get_network_topology(5, db, 5) # Assuming user_id=5 for vm_id=5 since logs show user_id: 5
    print(res)
except Exception as e:
    print("Error VM 5:", e)

print("Testing topology for VM 1...")
try:
    res = get_network_topology(1, db, 5) # user 5 might own vm 1 too
    print(res)
except Exception as e:
    print("Error VM 1:", e)
