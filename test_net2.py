import sys
import os

# Ensure vmledger package is discoverable
sys.path.insert(0, "/app")

from sqlalchemy.orm import Session
from vmledger.database import SessionLocal
from vmledger.api.network import get_network_topology

print("Testing topology for VM 5...")
db = SessionLocal()
try:
    res = get_network_topology(5, db, 5) # vm_id=5, user_id=5
    print("VM 5 Success!")
    print(res.dict())
except Exception as e:
    import traceback
    traceback.print_exc()

print("Testing topology for VM 1...")
try:
    res = get_network_topology(1, db, 5) # vm_id=1, user_id=5
    print("VM 1 Success!")
    print(res.dict())
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
