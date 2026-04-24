"""
Unit tests for VM Management API endpoints.

Tests VM CRUD operations, search functionality, and user isolation enforcement.

Requirements: 1.1-1.6, 3.1-3.5, 7.1-7.6, 11.1-11.5
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import fakeredis

from vmledger.main import app
from vmledger.services.auth_service import AuthService
from vmledger.services.vm_registry_service import VMRegistryService
from vmledger.models.user import User
from vmledger.models.vm import VM


@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def redis_client():
    """Provide a fake Redis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def auth_service(db_session, redis_client):
    """Provide an AuthService instance for testing."""
    return AuthService(db_session, redis_client)


@pytest.fixture
def vm_service(db_session):
    """Provide a VMRegistryService instance for testing."""
    return VMRegistryService(db_session)


@pytest.fixture
def user1(auth_service):
    """Create first test user."""
    return auth_service.register_user(
        username="user1",
        email="user1@example.com",
        password="ValidPass123!"
    )


@pytest.fixture
def user2(auth_service):
    """Create second test user for isolation testing."""
    return auth_service.register_user(
        username="user2",
        email="user2@example.com",
        password="ValidPass123!"
    )


@pytest.fixture
def auth_token_user1(auth_service, user1):
    """Get authentication token for user1."""
    result = auth_service.authenticate("user1", "ValidPass123!")
    return result["token"]


@pytest.fixture
def auth_token_user2(auth_service, user2):
    """Get authentication token for user2."""
    result = auth_service.authenticate("user2", "ValidPass123!")
    return result["token"]


@pytest.fixture
def sample_vm_data():
    """Provide sample VM registration data."""
    return {
        "ip_address": "192.168.1.100",
        "hostname": "web-server-01",
        "domain": "example.com",
        "ssh_port": 22,
        "tags": ["web", "production"],
        "deployment_notes": "# Web Server\n\nNginx 1.20 installed",
        "ssh_username": "root",
        "ssh_password": "test_password_123"
    }


@pytest.fixture
def created_vm(client, auth_token_user1, sample_vm_data):
    """Create a VM for testing."""
    response = client.post(
        "/api/vms",
        json=sample_vm_data,
        headers={"Authorization": f"Bearer {auth_token_user1}"}
    )
    assert response.status_code == 201
    return response.json()["data"]


class TestListVMsEndpoint:
    """Test GET /api/vms endpoint."""
    
    def test_list_vms_empty(self, client, auth_token_user1):
        """Test listing VMs when user has no VMs."""
        response = client.get(
            "/api/vms",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["vms"] == []
        assert data["data"]["total"] == 0
        assert data["data"]["page"] == 1
        assert data["data"]["per_page"] == 50
    
    def test_list_vms_with_data(self, client, auth_token_user1, created_vm):
        """Test listing VMs when user has VMs."""
        response = client.get(
            "/api/vms",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["vms"]) == 1
        assert data["data"]["total"] == 1
        assert data["data"]["vms"][0]["hostname"] == "web-server-01"
    
    def test_list_vms_pagination(self, client, auth_token_user1, created_vm):
        """Test VM list pagination."""
        response = client.get(
            "/api/vms?page=1&per_page=10",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["page"] == 1
        assert data["data"]["per_page"] == 10
    
    def test_list_vms_filter_by_tags(self, client, auth_token_user1, created_vm):
        """Test filtering VMs by tags."""
        response = client.get(
            "/api/vms?tags=web,production",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["vms"]) >= 1
    
    def test_list_vms_without_auth(self, client):
        """Test listing VMs without authentication."""
        response = client.get("/api/vms")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_list_vms_user_isolation(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that users only see their own VMs."""
        # User2 should not see User1's VM
        response = client.get(
            "/api/vms",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert len(data["data"]["vms"]) == 0


class TestCreateVMEndpoint:
    """Test POST /api/vms endpoint."""
    
    def test_create_vm_success(self, client, auth_token_user1, sample_vm_data):
        """Test successful VM creation."""
        response = client.post(
            "/api/vms",
            json=sample_vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["hostname"] == "web-server-01"
        assert data["data"]["ip_address"] == "192.168.1.100"
        assert data["data"]["ssh_port"] == 22
        assert data["data"]["tags"] == ["web", "production"]
        assert "id" in data["data"]
    
    def test_create_vm_invalid_ip(self, client, auth_token_user1, sample_vm_data):
        """Test VM creation with invalid IP address."""
        sample_vm_data["ip_address"] = "invalid-ip"
        
        response = client.post(
            "/api/vms",
            json=sample_vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_create_vm_invalid_port(self, client, auth_token_user1, sample_vm_data):
        """Test VM creation with invalid SSH port."""
        sample_vm_data["ssh_port"] = 70000  # Out of range
        
        response = client.post(
            "/api/vms",
            json=sample_vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_create_vm_duplicate(self, client, auth_token_user1, created_vm, sample_vm_data):
        """Test creating duplicate VM (same IP+port)."""
        response = client.post(
            "/api/vms",
            json=sample_vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "DUPLICATE_VM"
    
    def test_create_vm_without_credentials(self, client, auth_token_user1):
        """Test VM creation without credentials."""
        vm_data = {
            "ip_address": "192.168.1.101",
            "hostname": "test-server",
            "ssh_port": 22,
            "ssh_username": "root"
            # Missing both ssh_private_key and ssh_password
        }
        
        response = client.post(
            "/api/vms",
            json=vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_create_vm_without_auth(self, client, sample_vm_data):
        """Test VM creation without authentication."""
        response = client.post("/api/vms", json=sample_vm_data)
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data


class TestGetVMEndpoint:
    """Test GET /api/vms/{vm_id} endpoint."""
    
    def test_get_vm_success(self, client, auth_token_user1, created_vm):
        """Test successful VM retrieval."""
        vm_id = created_vm["id"]
        
        response = client.get(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["id"] == vm_id
        assert data["data"]["hostname"] == "web-server-01"
    
    def test_get_vm_not_found(self, client, auth_token_user1):
        """Test getting non-existent VM."""
        response = client.get(
            "/api/vms/99999",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_vm_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot access another user's VM."""
        vm_id = created_vm["id"]
        
        # User2 tries to access User1's VM
        response = client.get(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_vm_without_auth(self, client, created_vm):
        """Test getting VM without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data


class TestUpdateVMEndpoint:
    """Test PUT /api/vms/{vm_id} endpoint."""
    
    def test_update_vm_success(self, client, auth_token_user1, created_vm):
        """Test successful VM update."""
        vm_id = created_vm["id"]
        
        update_data = {
            "hostname": "updated-server",
            "tags": ["web", "staging"]
        }
        
        response = client.put(
            f"/api/vms/{vm_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["hostname"] == "updated-server"
        assert data["data"]["tags"] == ["web", "staging"]
    
    def test_update_vm_not_found(self, client, auth_token_user1):
        """Test updating non-existent VM."""
        update_data = {"hostname": "updated-server"}
        
        response = client.put(
            "/api/vms/99999",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_update_vm_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot update another user's VM."""
        vm_id = created_vm["id"]
        update_data = {"hostname": "hacked-server"}
        
        # User2 tries to update User1's VM
        response = client.put(
            f"/api/vms/{vm_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_update_vm_without_auth(self, client, created_vm):
        """Test updating VM without authentication."""
        vm_id = created_vm["id"]
        update_data = {"hostname": "updated-server"}
        
        response = client.put(f"/api/vms/{vm_id}", json=update_data)
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data


class TestDeleteVMEndpoint:
    """Test DELETE /api/vms/{vm_id} endpoint."""
    
    def test_delete_vm_success(self, client, auth_token_user1, created_vm):
        """Test successful VM deletion."""
        vm_id = created_vm["id"]
        
        response = client.delete(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data["data"]
        
        # Verify VM is deleted
        get_response = client.get(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        assert get_response.status_code == 404
    
    def test_delete_vm_not_found(self, client, auth_token_user1):
        """Test deleting non-existent VM."""
        response = client.delete(
            "/api/vms/99999",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_delete_vm_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot delete another user's VM."""
        vm_id = created_vm["id"]
        
        # User2 tries to delete User1's VM
        response = client.delete(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_delete_vm_without_auth(self, client, created_vm):
        """Test deleting VM without authentication."""
        vm_id = created_vm["id"]
        
        response = client.delete(f"/api/vms/{vm_id}")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data


class TestSearchVMsEndpoint:
    """Test GET /api/vms/search endpoint."""
    
    def test_search_vms_success(self, client, auth_token_user1, created_vm):
        """Test successful VM search."""
        response = client.get(
            "/api/vms/search?q=web",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "results" in data["data"]
        assert data["data"]["count"] >= 1
        assert data["data"]["query"] == "web"
    
    def test_search_vms_no_results(self, client, auth_token_user1, created_vm):
        """Test search with no matching results."""
        response = client.get(
            "/api/vms/search?q=nonexistent",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert data["data"]["results"] == []
    
    def test_search_vms_missing_query(self, client, auth_token_user1):
        """Test search without query parameter."""
        response = client.get(
            "/api/vms/search",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_search_vms_with_limit(self, client, auth_token_user1, created_vm):
        """Test search with result limit."""
        response = client.get(
            "/api/vms/search?q=web&limit=10",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["results"]) <= 10
    
    def test_search_vms_user_isolation(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that search respects user isolation."""
        # User2 searches for User1's VM
        response = client.get(
            "/api/vms/search?q=web-server-01",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["count"] == 0  # User2 should not see User1's VM
    
    def test_search_vms_without_auth(self, client):
        """Test search without authentication."""
        response = client.get("/api/vms/search?q=web")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data


class TestResponseFormat:
    """Test API response format consistency."""
    
    def test_success_response_format(self, client, auth_token_user1):
        """Test that success responses follow consistent format."""
        response = client.get(
            "/api/vms",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "request_id" in data
    
    def test_error_response_format(self, client, auth_token_user1):
        """Test that error responses follow consistent format."""
        response = client.get(
            "/api/vms/99999",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "request_id" in data


class TestIPAddressValidation:
    """Test IP address validation in VM creation."""
    
    @pytest.mark.parametrize("ip_address,should_succeed", [
        ("192.168.1.1", True),
        ("10.0.0.1", True),
        ("172.16.0.1", True),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", True),
        ("::1", True),
        ("invalid-ip", False),
        ("256.256.256.256", False),
        ("192.168.1", False),
    ])
    def test_ip_address_validation(self, client, auth_token_user1, ip_address, should_succeed):
        """Test various IP address formats."""
        vm_data = {
            "ip_address": ip_address,
            "hostname": "test-server",
            "ssh_port": 22,
            "ssh_username": "root",
            "ssh_password": "test_password"
        }
        
        response = client.post(
            "/api/vms",
            json=vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        if should_succeed:
            assert response.status_code == 201
        else:
            assert response.status_code == 400


class TestGetVMMetricsEndpoint:
    """Test GET /api/vms/{vm_id}/metrics endpoint."""
    
    def test_get_metrics_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful metrics retrieval."""
        from vmledger.models.metric import Metric
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test metrics
        metric1 = Metric(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            cpu_usage_percent=45.5,
            ram_used_mb=2048,
            ram_total_mb=4096,
            disk_used_gb=50.0,
            disk_total_gb=100.0,
            disk_usage_percent=50.0,
            collection_success=True
        )
        db_session.add(metric1)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/metrics",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "metrics" in data["data"]
        assert data["data"]["count"] >= 1
        assert data["data"]["vm_id"] == vm_id
        
        # Check metric data structure
        metric = data["data"]["metrics"][0]
        assert "timestamp" in metric
        assert "cpu_usage_percent" in metric
        assert "ram_used_mb" in metric
        assert "collection_success" in metric
    
    def test_get_metrics_with_limit(self, client, auth_token_user1, created_vm, db_session):
        """Test metrics retrieval with limit parameter."""
        from vmledger.models.metric import Metric
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create multiple test metrics
        for i in range(5):
            metric = Metric(
                vm_id=vm_id,
                timestamp=datetime.utcnow(),
                cpu_usage_percent=float(i * 10),
                ram_used_mb=1024,
                ram_total_mb=4096,
                disk_used_gb=50.0,
                disk_total_gb=100.0,
                disk_usage_percent=50.0,
                collection_success=True
            )
            db_session.add(metric)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/metrics?limit=3",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["metrics"]) <= 3
    
    def test_get_metrics_vm_not_found(self, client, auth_token_user1):
        """Test getting metrics for non-existent VM."""
        response = client.get(
            "/api/vms/99999/metrics",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_metrics_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot access another user's VM metrics."""
        vm_id = created_vm["id"]
        
        # User2 tries to access User1's VM metrics
        response = client.get(
            f"/api/vms/{vm_id}/metrics",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_metrics_without_auth(self, client, created_vm):
        """Test getting metrics without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}/metrics")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False


class TestGetVMPingHistoryEndpoint:
    """Test GET /api/vms/{vm_id}/ping endpoint."""
    
    def test_get_ping_history_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful ping history retrieval."""
        from vmledger.models.ping_result import PingResult
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test ping results
        ping1 = PingResult(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            success=True,
            response_time_ms=25.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        db_session.add(ping1)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/ping",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "ping_results" in data["data"]
        assert data["data"]["count"] >= 1
        assert data["data"]["vm_id"] == vm_id
        
        # Check ping result data structure
        ping = data["data"]["ping_results"][0]
        assert "timestamp" in ping
        assert "success" in ping
        assert "response_time_ms" in ping
        assert "icmp_success" in ping
        assert "tcp_success" in ping
    
    def test_get_ping_history_with_limit(self, client, auth_token_user1, created_vm, db_session):
        """Test ping history retrieval with limit parameter."""
        from vmledger.models.ping_result import PingResult
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create multiple test ping results
        for i in range(5):
            ping = PingResult(
                vm_id=vm_id,
                timestamp=datetime.utcnow(),
                success=True,
                response_time_ms=float(i * 10),
                error_type=None,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/ping?limit=3",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["ping_results"]) <= 3
    
    def test_get_ping_history_vm_not_found(self, client, auth_token_user1):
        """Test getting ping history for non-existent VM."""
        response = client.get(
            "/api/vms/99999/ping",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_ping_history_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot access another user's VM ping history."""
        vm_id = created_vm["id"]
        
        # User2 tries to access User1's VM ping history
        response = client.get(
            f"/api/vms/{vm_id}/ping",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_ping_history_without_auth(self, client, created_vm):
        """Test getting ping history without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}/ping")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False


class TestGetVMStatusEndpoint:
    """Test GET /api/vms/{vm_id}/status endpoint."""
    
    def test_get_status_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful VM status retrieval."""
        from vmledger.models.ping_result import PingResult
        from vmledger.models.metric import Metric
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test ping result
        ping = PingResult(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            success=True,
            response_time_ms=25.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        db_session.add(ping)
        
        # Create test metric
        metric = Metric(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            cpu_usage_percent=45.5,
            ram_used_mb=2048,
            ram_total_mb=4096,
            disk_used_gb=50.0,
            disk_total_gb=100.0,
            disk_usage_percent=50.0,
            collection_success=True
        )
        db_session.add(metric)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/status",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        # Check VM info
        assert "vm" in data["data"]
        assert data["data"]["vm"]["id"] == vm_id
        assert "hostname" in data["data"]["vm"]
        assert "is_reachable" in data["data"]["vm"]
        
        # Check latest ping
        assert "latest_ping" in data["data"]
        assert data["data"]["latest_ping"] is not None
        assert "success" in data["data"]["latest_ping"]
        
        # Check latest metrics
        assert "latest_metrics" in data["data"]
        assert data["data"]["latest_metrics"] is not None
        assert "cpu_usage_percent" in data["data"]["latest_metrics"]
    
    def test_get_status_no_monitoring_data(self, client, auth_token_user1, created_vm):
        """Test VM status retrieval when no monitoring data exists."""
        vm_id = created_vm["id"]
        
        response = client.get(
            f"/api/vms/{vm_id}/status",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "vm" in data["data"]
        assert data["data"]["latest_ping"] is None
        assert data["data"]["latest_metrics"] is None
    
    def test_get_status_vm_not_found(self, client, auth_token_user1):
        """Test getting status for non-existent VM."""
        response = client.get(
            "/api/vms/99999/status",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_status_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that user cannot access another user's VM status."""
        vm_id = created_vm["id"]
        
        # User2 tries to access User1's VM status
        response = client.get(
            f"/api/vms/{vm_id}/status",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_status_without_auth(self, client, created_vm):
        """Test getting status without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}/status")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False



class TestGetAlertConfigEndpoint:
    """Test GET /api/vms/{vm_id}/alerts/config endpoint."""
    
    def test_get_alert_config_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful alert config retrieval."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com",
            cooldown_minutes=15
        )
        db_session.add(alert_config)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/alerts/config",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["vm_id"] == vm_id
        assert data["data"]["enabled"] is True
        assert data["data"]["webhook_url"] == "https://example.com/webhook"
        assert data["data"]["email_recipient"] == "admin@example.com"
        assert data["data"]["cooldown_minutes"] == 15
        assert "created_at" in data["data"]
        assert "updated_at" in data["data"]
    
    def test_get_alert_config_not_found(self, client, auth_token_user1, created_vm):
        """Test getting alert config when it doesn't exist."""
        vm_id = created_vm["id"]
        
        response = client.get(
            f"/api/vms/{vm_id}/alerts/config",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "ALERT_CONFIG_NOT_FOUND"
    
    def test_get_alert_config_vm_not_found(self, client, auth_token_user1):
        """Test getting alert config for non-existent VM."""
        response = client.get(
            "/api/vms/99999/alerts/config",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_alert_config_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm, db_session):
        """Test that user cannot access another user's VM alert config."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # User2 tries to access User1's VM alert config
        response = client.get(
            f"/api/vms/{vm_id}/alerts/config",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_alert_config_without_auth(self, client, created_vm):
        """Test getting alert config without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}/alerts/config")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False


class TestUpdateAlertConfigEndpoint:
    """Test PUT /api/vms/{vm_id}/alerts/config endpoint."""
    
    def test_update_alert_config_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful alert config update."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com",
            cooldown_minutes=15
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Update config
        update_data = {
            "enabled": False,
            "webhook_url": "https://newurl.com/webhook",
            "cooldown_minutes": 30
        }
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["enabled"] is False
        assert data["data"]["webhook_url"] == "https://newurl.com/webhook"
        assert data["data"]["email_recipient"] == "admin@example.com"  # Unchanged
        assert data["data"]["cooldown_minutes"] == 30
    
    def test_update_alert_config_partial_update(self, client, auth_token_user1, created_vm, db_session):
        """Test partial alert config update."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com",
            cooldown_minutes=15
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Update only enabled field
        update_data = {"enabled": False}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["enabled"] is False
        assert data["data"]["webhook_url"] == "https://example.com/webhook"  # Unchanged
    
    def test_update_alert_config_invalid_webhook_url(self, client, auth_token_user1, created_vm, db_session):
        """Test updating alert config with invalid webhook URL."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with invalid webhook URL
        update_data = {"webhook_url": "not-a-valid-url"}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "http" in data["error"]["message"].lower()
    
    def test_update_alert_config_invalid_email(self, client, auth_token_user1, created_vm, db_session):
        """Test updating alert config with invalid email."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with invalid email
        update_data = {"email_recipient": "not-an-email"}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "email" in data["error"]["message"].lower()
    
    def test_update_alert_config_invalid_cooldown(self, client, auth_token_user1, created_vm, db_session):
        """Test updating alert config with invalid cooldown period."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with invalid cooldown (out of range)
        update_data = {"cooldown_minutes": 2000}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "cooldown" in data["error"]["message"].lower()
    
    def test_update_alert_config_remove_all_methods(self, client, auth_token_user1, created_vm, db_session):
        """Test that at least one notification method must be configured."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to remove both notification methods
        update_data = {
            "webhook_url": None,
            "email_recipient": None
        }
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "notification method" in data["error"]["message"].lower()
    
    def test_update_alert_config_not_found(self, client, auth_token_user1, created_vm):
        """Test updating alert config when it doesn't exist."""
        vm_id = created_vm["id"]
        
        update_data = {"enabled": False}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "ALERT_CONFIG_NOT_FOUND"
    
    def test_update_alert_config_vm_not_found(self, client, auth_token_user1):
        """Test updating alert config for non-existent VM."""
        update_data = {"enabled": False}
        
        response = client.put(
            "/api/vms/99999/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_update_alert_config_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm, db_session):
        """Test that user cannot update another user's VM alert config."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # User2 tries to update User1's VM alert config
        update_data = {"enabled": False}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_update_alert_config_without_auth(self, client, created_vm):
        """Test updating alert config without authentication."""
        vm_id = created_vm["id"]
        update_data = {"enabled": False}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data
        )
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False


class TestGetAlertHistoryEndpoint:
    """Test GET /api/vms/{vm_id}/alerts/history endpoint."""
    
    def test_get_alert_history_success(self, client, auth_token_user1, created_vm, db_session):
        """Test successful alert history retrieval."""
        from vmledger.models.alert import Alert
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test alerts
        alert1 = Alert(
            vm_id=vm_id,
            alert_type="VM_UNREACHABLE",
            sent_at=datetime.utcnow(),
            notification_method="webhook",
            success=True,
            error_message=None
        )
        alert2 = Alert(
            vm_id=vm_id,
            alert_type="VM_RECOVERED",
            sent_at=datetime.utcnow(),
            notification_method="email",
            success=True,
            error_message=None
        )
        db_session.add(alert1)
        db_session.add(alert2)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/alerts/history",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "alerts" in data["data"]
        assert data["data"]["count"] >= 2
        assert data["data"]["vm_id"] == vm_id
        
        # Check alert data structure
        alert = data["data"]["alerts"][0]
        assert "id" in alert
        assert "vm_id" in alert
        assert "alert_type" in alert
        assert "sent_at" in alert
        assert "notification_method" in alert
        assert "success" in alert
    
    def test_get_alert_history_with_limit(self, client, auth_token_user1, created_vm, db_session):
        """Test alert history retrieval with limit parameter."""
        from vmledger.models.alert import Alert
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create multiple test alerts
        for i in range(5):
            alert = Alert(
                vm_id=vm_id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow(),
                notification_method="webhook",
                success=True
            )
            db_session.add(alert)
        db_session.commit()
        
        response = client.get(
            f"/api/vms/{vm_id}/alerts/history?limit=3",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["alerts"]) <= 3
    
    def test_get_alert_history_empty(self, client, auth_token_user1, created_vm):
        """Test alert history retrieval when no alerts exist."""
        vm_id = created_vm["id"]
        
        response = client.get(
            f"/api/vms/{vm_id}/alerts/history",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert data["data"]["alerts"] == []
    
    def test_get_alert_history_vm_not_found(self, client, auth_token_user1):
        """Test getting alert history for non-existent VM."""
        response = client.get(
            "/api/vms/99999/alerts/history",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "VM_NOT_FOUND"
    
    def test_get_alert_history_unauthorized_access(self, client, auth_token_user1, auth_token_user2, created_vm, db_session):
        """Test that user cannot access another user's VM alert history."""
        from vmledger.models.alert import Alert
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test alert
        alert = Alert(
            vm_id=vm_id,
            alert_type="VM_UNREACHABLE",
            sent_at=datetime.utcnow(),
            notification_method="webhook",
            success=True
        )
        db_session.add(alert)
        db_session.commit()
        
        # User2 tries to access User1's VM alert history
        response = client.get(
            f"/api/vms/{vm_id}/alerts/history",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
    
    def test_get_alert_history_without_auth(self, client, created_vm):
        """Test getting alert history without authentication."""
        vm_id = created_vm["id"]
        
        response = client.get(f"/api/vms/{vm_id}/alerts/history")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False


class TestAlertConfigValidation:
    """Test alert configuration validation."""
    
    @pytest.mark.parametrize("webhook_url,should_succeed", [
        ("https://example.com/webhook", True),
        ("http://example.com/webhook", True),
        ("https://api.example.com/v1/alerts", True),
        ("ftp://example.com/webhook", False),
        ("not-a-url", False),
        ("example.com/webhook", False),
    ])
    def test_webhook_url_validation(self, client, auth_token_user1, created_vm, db_session, webhook_url, should_succeed):
        """Test various webhook URL formats."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with test webhook URL
        update_data = {"webhook_url": webhook_url}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        if should_succeed:
            assert response.status_code == 200
        else:
            assert response.status_code == 400
    
    @pytest.mark.parametrize("email,should_succeed", [
        ("admin@example.com", True),
        ("user.name@example.com", True),
        ("user+tag@example.co.uk", True),
        ("invalid-email", False),
        ("@example.com", False),
        ("user@", False),
        ("user@.com", False),
    ])
    def test_email_validation(self, client, auth_token_user1, created_vm, db_session, email, should_succeed):
        """Test various email formats."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with test email
        update_data = {"email_recipient": email}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        if should_succeed:
            assert response.status_code == 200
        else:
            assert response.status_code == 400
    
    @pytest.mark.parametrize("cooldown,should_succeed", [
        (1, True),
        (15, True),
        (60, True),
        (1440, True),
        (0, False),
        (-1, False),
        (1441, False),
        (10000, False),
    ])
    def test_cooldown_validation(self, client, auth_token_user1, created_vm, db_session, cooldown, should_succeed):
        """Test various cooldown period values."""
        from vmledger.models.alert_config import AlertConfig
        
        vm_id = created_vm["id"]
        
        # Create alert config
        alert_config = AlertConfig(
            vm_id=vm_id,
            enabled=True,
            webhook_url="https://example.com/webhook",
            email_recipient="admin@example.com"
        )
        db_session.add(alert_config)
        db_session.commit()
        
        # Try to update with test cooldown
        update_data = {"cooldown_minutes": cooldown}
        
        response = client.put(
            f"/api/vms/{vm_id}/alerts/config",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        if should_succeed:
            assert response.status_code == 200
        else:
            assert response.status_code == 400



class TestGetDashboardEndpoint:
    """Test GET /api/dashboard endpoint."""
    
    def test_get_dashboard_empty(self, client, auth_token_user1):
        """Test dashboard when user has no VMs."""
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["vms"] == []
        assert data["data"]["total_vms"] == 0
        assert data["data"]["reachable_vms"] == 0
        assert data["data"]["unreachable_vms"] == 0
    
    def test_get_dashboard_with_vms(self, client, auth_token_user1, created_vm):
        """Test dashboard with VMs."""
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["vms"]) == 1
        assert data["data"]["total_vms"] == 1
        
        # Check VM data structure
        vm = data["data"]["vms"][0]
        assert "id" in vm
        assert "hostname" in vm
        assert "ip_address" in vm
        assert "ssh_port" in vm
        assert "tags" in vm
        assert "is_reachable" in vm
        assert "latest_ping" in vm
        assert "latest_metrics" in vm
    
    def test_get_dashboard_with_metrics(self, client, auth_token_user1, created_vm, db_session):
        """Test dashboard includes latest metrics."""
        from vmledger.models.metric import Metric
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test metric
        metric = Metric(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            cpu_usage_percent=45.5,
            ram_used_mb=2048,
            ram_total_mb=4096,
            disk_used_gb=50.0,
            disk_total_gb=100.0,
            disk_usage_percent=50.0,
            collection_success=True
        )
        db_session.add(metric)
        db_session.commit()
        
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        vm = data["data"]["vms"][0]
        assert vm["latest_metrics"] is not None
        assert vm["latest_metrics"]["cpu_usage_percent"] == 45.5
        assert vm["latest_metrics"]["ram_used_mb"] == 2048
        assert vm["latest_metrics"]["disk_usage_percent"] == 50.0
    
    def test_get_dashboard_with_ping_results(self, client, auth_token_user1, created_vm, db_session):
        """Test dashboard includes latest ping results."""
        from vmledger.models.ping_result import PingResult
        from datetime import datetime
        
        vm_id = created_vm["id"]
        
        # Create test ping result
        ping = PingResult(
            vm_id=vm_id,
            timestamp=datetime.utcnow(),
            success=True,
            response_time_ms=25.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        db_session.add(ping)
        db_session.commit()
        
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        vm = data["data"]["vms"][0]
        assert vm["latest_ping"] is not None
        assert vm["latest_ping"]["success"] is True
        assert vm["latest_ping"]["response_time_ms"] == 25.5
    
    def test_get_dashboard_user_isolation(self, client, auth_token_user1, auth_token_user2, created_vm):
        """Test that dashboard respects user isolation."""
        # User2 should not see User1's VMs
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user2}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_vms"] == 0
        assert len(data["data"]["vms"]) == 0
    
    def test_get_dashboard_without_auth(self, client):
        """Test dashboard without authentication."""
        response = client.get("/api/dashboard")
        
        assert response.status_code == 401
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
    
    def test_get_dashboard_multiple_vms(self, client, auth_token_user1, sample_vm_data, db_session):
        """Test dashboard with multiple VMs."""
        from vmledger.services.vm_registry_service import VMRegistryService
        from vmledger.schemas.vm_schemas import VMCreateSchema
        
        # Create multiple VMs
        vm_service = VMRegistryService(db_session)
        
        # Get user_id from token
        from jose import jwt
        from vmledger.config import settings
        
        # Decode token to get user_id
        payload = jwt.decode(
            auth_token_user1,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
        
        # Create VMs with different IPs
        for i in range(3):
            vm_data = VMCreateSchema(
                ip_address=f"192.168.1.{100 + i}",
                hostname=f"server-{i}",
                ssh_port=22,
                ssh_username="root",
                ssh_password="test_password"
            )
            vm_service.create_vm(user_id, vm_data)
        
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_vms"] == 3
        assert len(data["data"]["vms"]) == 3
    
    def test_get_dashboard_reachability_counts(self, client, auth_token_user1, created_vm, db_session):
        """Test dashboard calculates reachability counts correctly."""
        from vmledger.models.vm import VM
        from vmledger.services.vm_registry_service import VMRegistryService
        from vmledger.schemas.vm_schemas import VMCreateSchema
        
        # Get user_id
        from jose import jwt
        from vmledger.config import settings
        
        payload = jwt.decode(
            auth_token_user1,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
        
        # Create another VM
        vm_service = VMRegistryService(db_session)
        vm2_data = VMCreateSchema(
            ip_address="192.168.1.101",
            hostname="server-2",
            ssh_port=22,
            ssh_username="root",
            ssh_password="test_password"
        )
        vm2 = vm_service.create_vm(user_id, vm2_data)
        
        # Update reachability status
        vm1 = db_session.query(VM).filter(VM.id == created_vm["id"]).first()
        vm1.is_reachable = True
        vm2.is_reachable = False
        db_session.commit()
        
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_vms"] == 2
        assert data["data"]["reachable_vms"] == 1
        assert data["data"]["unreachable_vms"] == 1
    
    def test_get_dashboard_caching(self, client, auth_token_user1, created_vm):
        """Test that dashboard data is cached."""
        # First request - should not be cached
        response1 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request - should be cached (if Redis is available)
        response2 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Data should be the same
        assert data1["data"]["total_vms"] == data2["data"]["total_vms"]
        assert len(data1["data"]["vms"]) == len(data2["data"]["vms"])
    
    def test_get_dashboard_cache_invalidation_on_create(self, client, auth_token_user1, sample_vm_data):
        """Test that cache is invalidated when VM is created."""
        # Get initial dashboard
        response1 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response1.status_code == 200
        initial_count = response1.json()["data"]["total_vms"]
        
        # Create a new VM
        response2 = client.post(
            "/api/vms",
            json=sample_vm_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response2.status_code == 201
        
        # Get dashboard again - should reflect new VM
        response3 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response3.status_code == 200
        new_count = response3.json()["data"]["total_vms"]
        
        assert new_count == initial_count + 1
    
    def test_get_dashboard_cache_invalidation_on_update(self, client, auth_token_user1, created_vm):
        """Test that cache is invalidated when VM is updated."""
        vm_id = created_vm["id"]
        
        # Get initial dashboard
        response1 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response1.status_code == 200
        initial_hostname = response1.json()["data"]["vms"][0]["hostname"]
        
        # Update VM
        update_data = {"hostname": "updated-hostname"}
        response2 = client.put(
            f"/api/vms/{vm_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response2.status_code == 200
        
        # Get dashboard again - should reflect updated hostname
        response3 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response3.status_code == 200
        new_hostname = response3.json()["data"]["vms"][0]["hostname"]
        
        assert new_hostname == "updated-hostname"
        assert new_hostname != initial_hostname
    
    def test_get_dashboard_cache_invalidation_on_delete(self, client, auth_token_user1, created_vm):
        """Test that cache is invalidated when VM is deleted."""
        vm_id = created_vm["id"]
        
        # Get initial dashboard
        response1 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response1.status_code == 200
        initial_count = response1.json()["data"]["total_vms"]
        
        # Delete VM
        response2 = client.delete(
            f"/api/vms/{vm_id}",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response2.status_code == 200
        
        # Get dashboard again - should reflect deleted VM
        response3 = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response3.status_code == 200
        new_count = response3.json()["data"]["total_vms"]
        
        assert new_count == initial_count - 1
        assert new_count == 0
    
    def test_get_dashboard_response_format(self, client, auth_token_user1, created_vm):
        """Test dashboard response format is correct."""
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "request_id" in data
        assert "cached" in data
        
        # Check data structure
        assert "vms" in data["data"]
        assert "total_vms" in data["data"]
        assert "reachable_vms" in data["data"]
        assert "unreachable_vms" in data["data"]
        
        # Check VM structure
        if len(data["data"]["vms"]) > 0:
            vm = data["data"]["vms"][0]
            required_fields = [
                "id", "ip_address", "hostname", "ssh_port", "tags",
                "is_reachable", "last_seen", "created_at", "updated_at",
                "latest_ping", "latest_metrics"
            ]
            for field in required_fields:
                assert field in vm
    
    def test_get_dashboard_performance(self, client, auth_token_user1, sample_vm_data, db_session):
        """Test dashboard performance with multiple VMs."""
        from vmledger.services.vm_registry_service import VMRegistryService
        from vmledger.schemas.vm_schemas import VMCreateSchema
        from vmledger.services.auth_service import AuthService
        import fakeredis
        import time
        from jose import jwt
        from vmledger.config import settings
        
        # Get user_id
        payload = jwt.decode(
            auth_token_user1,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
        
        # Create 10 VMs
        vm_service = VMRegistryService(db_session)
        for i in range(10):
            vm_data = VMCreateSchema(
                ip_address=f"192.168.1.{100 + i}",
                hostname=f"server-{i}",
                ssh_port=22,
                ssh_username="root",
                ssh_password="test_password"
            )
            vm_service.create_vm(user_id, vm_data)
        
        # Measure response time
        start_time = time.time()
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": f"Bearer {auth_token_user1}"}
        )
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500  # Should respond within 500ms
        
        data = response.json()
        assert data["data"]["total_vms"] == 10
