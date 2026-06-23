import sys
from fastapi.testclient import TestClient
from vmledger.main import app
from vmledger.database import SessionLocal
from vmledger.models.user import User

client = TestClient(app)

db = SessionLocal()
user = db.query(User).first()

from vmledger.services.auth_service import AuthService
from datetime import timedelta

auth_service = AuthService(db)
access_token = auth_service._create_access_token(
    data={"sub": str(user.id), "username": user.username, "email": user.email, "type": "access"}
)

print("Making HTTP request to /api/vms/5/network/topology...")
try:
    response = client.get(
        "/api/vms/5/network/topology", 
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print(f"Status VM 5: {response.status_code}")
    print(f"Response VM 5: {response.text[:200]}")
except Exception as e:
    import traceback
    traceback.print_exc()
