from dotenv import load_dotenv
load_dotenv()
from vmledger.database import SessionLocal
from vmledger.services.vm_registry_service import VMRegistryService
db = SessionLocal()
service = VMRegistryService(db)
try:
    print(service.list_vms_with_latest_metrics(1))
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
