"""
Unit tests for VMRegistryService.

Tests CRUD operations, user isolation, duplicate detection, and cascade deletion.

Requirements: 1.1-1.6, 3.1-3.5, 11.1-11.5
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from vmledger.services.vm_registry_service import (
    VMRegistryService,
    DuplicateVMError,
    VMNotFoundError,
    UnauthorizedAccessError
)
from vmledger.services.credential_manager import InvalidSSHKeyError
from vmledger.schemas.vm_schemas import VMCreateSchema, VMUpdateSchema, VMFilters
from vmledger.models.vm import VM
from vmledger.models.user import User
from vmledger.models.credential import Credential
from vmledger.models.ping_result import PingResult
from vmledger.models.metric import Metric
from vmledger.models.alert import Alert


# Test fixtures

@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        encryption_salt="test_salt_12345678901234567890123456789012"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user2(db_session: Session) -> User:
    """Create a second test user for isolation tests."""
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash="hashed_password",
        encryption_salt="test_salt2_1234567890123456789012345678901"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def vm_registry_service(db_session: Session) -> VMRegistryService:
    """Create VMRegistryService instance."""
    return VMRegistryService(db_session)


@pytest.fixture
def valid_ssh_key() -> str:
    """Return a valid SSH private key for testing."""
    # Generate a real RSA key using Paramiko
    import paramiko
    from io import StringIO
    
    key = paramiko.RSAKey.generate(2048)
    key_file = StringIO()
    key.write_private_key(key_file)
    key_file.seek(0)
    return key_file.read()


# Test create_vm

def test_create_vm_with_ssh_key(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test creating a VM with SSH key authentication."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        domain="example.com",
        ssh_port=22,
        tags=["web", "production"],
        deployment_notes="# Test VM\nNginx server",
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    assert vm.id is not None
    assert vm.user_id == test_user.id
    assert vm.ip_address == "192.168.1.100"
    assert vm.hostname == "test-vm"
    assert vm.domain == "example.com"
    assert vm.ssh_port == 22
    assert vm.tags == ["web", "production"]
    assert vm.deployment_notes == "# Test VM\nNginx server"
    assert vm.is_reachable is None
    
    # Verify credential was created
    credential = db_session.query(Credential).filter(Credential.vm_id == vm.id).first()
    assert credential is not None
    assert credential.auth_type == "ssh_key"
    assert credential.ssh_username == "root"
    assert credential.encrypted_credential is not None


def test_create_vm_with_password(vm_registry_service, test_user, db_session):
    """Test creating a VM with password authentication."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.101",
        hostname="test-vm-2",
        ssh_port=2222,
        tags=[],
        ssh_username="admin",
        ssh_password="SecurePassword123!"
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    assert vm.id is not None
    assert vm.ip_address == "192.168.1.101"
    assert vm.ssh_port == 2222
    
    # Verify credential was created with password
    credential = db_session.query(Credential).filter(Credential.vm_id == vm.id).first()
    assert credential is not None
    assert credential.auth_type == "password"
    assert credential.ssh_username == "admin"


def test_create_vm_duplicate_rejected(vm_registry_service, test_user, valid_ssh_key):
    """Test that duplicate VM registration is rejected (Requirement 1.6)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    # First registration succeeds
    vm1 = vm_registry_service.create_vm(test_user.id, vm_data)
    assert vm1.id is not None
    
    # Second registration with same IP+port fails
    with pytest.raises(DuplicateVMError) as exc_info:
        vm_registry_service.create_vm(test_user.id, vm_data)
    
    assert "already exists" in str(exc_info.value).lower()


def test_create_vm_different_port_allowed(vm_registry_service, test_user, valid_ssh_key):
    """Test that same IP with different port is allowed."""
    vm_data1 = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm-1",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm_data2 = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm-2",
        ssh_port=2222,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm1 = vm_registry_service.create_vm(test_user.id, vm_data1)
    vm2 = vm_registry_service.create_vm(test_user.id, vm_data2)
    
    assert vm1.id != vm2.id
    assert vm1.ip_address == vm2.ip_address
    assert vm1.ssh_port != vm2.ssh_port


def test_create_vm_invalid_ssh_key(vm_registry_service, test_user):
    """Test that invalid SSH key is rejected (Requirement 2.5)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key="invalid_key_data"
    )
    
    with pytest.raises(InvalidSSHKeyError):
        vm_registry_service.create_vm(test_user.id, vm_data)


def test_create_vm_max_tags(vm_registry_service, test_user, valid_ssh_key):
    """Test that max 20 tags are allowed (Requirement 6.5)."""
    # Exactly 20 tags should succeed
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        tags=[f"tag{i}" for i in range(20)],
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    assert len(vm.tags) == 20


def test_create_vm_deployment_notes_max_length(vm_registry_service, test_user, valid_ssh_key):
    """Test deployment notes at max length (Requirement 6.4)."""
    # Exactly 50,000 characters should succeed
    notes = "a" * 50000
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        deployment_notes=notes,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    assert len(vm.deployment_notes) == 50000


# Test get_vm

def test_get_vm_success(vm_registry_service, test_user, valid_ssh_key):
    """Test retrieving a VM by ID."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    created_vm = vm_registry_service.create_vm(test_user.id, vm_data)
    retrieved_vm = vm_registry_service.get_vm(test_user.id, created_vm.id)
    
    assert retrieved_vm.id == created_vm.id
    assert retrieved_vm.hostname == "test-vm"


def test_get_vm_not_found(vm_registry_service, test_user):
    """Test retrieving non-existent VM."""
    with pytest.raises(VMNotFoundError):
        vm_registry_service.get_vm(test_user.id, 99999)


def test_get_vm_unauthorized_access(vm_registry_service, test_user, test_user2, valid_ssh_key):
    """Test user isolation - cannot access other user's VM (Requirement 3.1)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    # User 1 creates VM
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    # User 2 cannot access it
    with pytest.raises(UnauthorizedAccessError):
        vm_registry_service.get_vm(test_user2.id, vm.id)


# Test list_vms

def test_list_vms_user_isolation(vm_registry_service, test_user, test_user2, valid_ssh_key):
    """Test that users only see their own VMs (Requirement 3.1)."""
    # User 1 creates 2 VMs
    for i in range(2):
        vm_data = VMCreateSchema(
            ip_address=f"192.168.1.{100+i}",
            hostname=f"user1-vm-{i}",
            ssh_port=22,
            ssh_username="root",
            ssh_private_key=valid_ssh_key
        )
        vm_registry_service.create_vm(test_user.id, vm_data)
    
    # User 2 creates 1 VM
    vm_data = VMCreateSchema(
        ip_address="192.168.1.200",
        hostname="user2-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm_registry_service.create_vm(test_user2.id, vm_data)
    
    # User 1 should see only their 2 VMs
    result1 = vm_registry_service.list_vms(test_user.id)
    assert result1["total"] == 2
    assert len(result1["vms"]) == 2
    
    # User 2 should see only their 1 VM
    result2 = vm_registry_service.list_vms(test_user2.id)
    assert result2["total"] == 1
    assert len(result2["vms"]) == 1
    assert result2["vms"][0].hostname == "user2-vm"


def test_list_vms_pagination(vm_registry_service, test_user, valid_ssh_key):
    """Test VM list pagination."""
    # Create 5 VMs
    for i in range(5):
        vm_data = VMCreateSchema(
            ip_address=f"192.168.1.{100+i}",
            hostname=f"vm-{i}",
            ssh_port=22,
            ssh_username="root",
            ssh_private_key=valid_ssh_key
        )
        vm_registry_service.create_vm(test_user.id, vm_data)
    
    # Get page 1 with 2 items per page
    filters = VMFilters(page=1, per_page=2)
    result = vm_registry_service.list_vms(test_user.id, filters)
    
    assert result["total"] == 5
    assert len(result["vms"]) == 2
    assert result["page"] == 1
    assert result["per_page"] == 2
    assert result["pages"] == 3


def test_list_vms_filter_by_tags(vm_registry_service, test_user, valid_ssh_key):
    """Test filtering VMs by tags."""
    # Create VMs with different tags
    vm_data1 = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="web-vm",
        ssh_port=22,
        tags=["web", "production"],
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm_registry_service.create_vm(test_user.id, vm_data1)
    
    vm_data2 = VMCreateSchema(
        ip_address="192.168.1.101",
        hostname="db-vm",
        ssh_port=22,
        tags=["database", "production"],
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm_registry_service.create_vm(test_user.id, vm_data2)
    
    # Filter by "web" tag
    filters = VMFilters(tags=["web"])
    result = vm_registry_service.list_vms(test_user.id, filters)
    
    assert result["total"] == 1
    assert result["vms"][0].hostname == "web-vm"


# Test update_vm

def test_update_vm_success(vm_registry_service, test_user, valid_ssh_key):
    """Test updating a VM (Requirement 11.1)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    # Update hostname and tags
    updates = VMUpdateSchema(
        hostname="updated-vm",
        tags=["updated", "test"]
    )
    
    updated_vm = vm_registry_service.update_vm(test_user.id, vm.id, updates)
    
    assert updated_vm.hostname == "updated-vm"
    assert updated_vm.tags == ["updated", "test"]
    assert updated_vm.ip_address == "192.168.1.100"  # Unchanged


def test_update_vm_unauthorized(vm_registry_service, test_user, test_user2, valid_ssh_key):
    """Test that users cannot update other users' VMs (Requirement 3.2)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    updates = VMUpdateSchema(hostname="hacked-vm")
    
    with pytest.raises(UnauthorizedAccessError):
        vm_registry_service.update_vm(test_user2.id, vm.id, updates)


def test_update_vm_duplicate_check(vm_registry_service, test_user, valid_ssh_key):
    """Test that update prevents duplicate IP+port."""
    # Create two VMs
    vm_data1 = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="vm1",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm1 = vm_registry_service.create_vm(test_user.id, vm_data1)
    
    vm_data2 = VMCreateSchema(
        ip_address="192.168.1.101",
        hostname="vm2",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm2 = vm_registry_service.create_vm(test_user.id, vm_data2)
    
    # Try to update vm2 to have same IP as vm1
    updates = VMUpdateSchema(ip_address="192.168.1.100")
    
    with pytest.raises(DuplicateVMError):
        vm_registry_service.update_vm(test_user.id, vm2.id, updates)


def test_update_vm_credentials(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test updating VM credentials (Requirement 11.2)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_password="OldPassword123!"
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    # Update to use SSH key instead
    updates = VMUpdateSchema(ssh_private_key=valid_ssh_key)
    updated_vm = vm_registry_service.update_vm(test_user.id, vm.id, updates)
    
    # Verify credential was updated
    credential = db_session.query(Credential).filter(Credential.vm_id == vm.id).first()
    assert credential.auth_type == "ssh_key"


# Test delete_vm

def test_delete_vm_success(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test deleting a VM (Requirement 11.3)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    vm_id = vm.id
    
    # Delete VM
    result = vm_registry_service.delete_vm(test_user.id, vm_id)
    assert result is True
    
    # Verify VM is deleted
    deleted_vm = db_session.query(VM).filter(VM.id == vm_id).first()
    assert deleted_vm is None


def test_delete_vm_cascade_deletion(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test cascade deletion of credentials and monitoring data (Requirement 11.4)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    vm_id = vm.id
    
    # Add some monitoring data
    ping_result = PingResult(
        vm_id=vm_id,
        success=True,
        response_time_ms=10.5,
        icmp_success=True,
        tcp_success=True
    )
    db_session.add(ping_result)
    
    metric = Metric(
        vm_id=vm_id,
        cpu_usage_percent=50.0,
        ram_used_mb=2048,
        ram_total_mb=4096,
        disk_used_gb=50.0,
        disk_total_gb=100.0,
        disk_usage_percent=50.0,
        collection_success=True
    )
    db_session.add(metric)
    
    alert = Alert(
        vm_id=vm_id,
        alert_type="VM_UNREACHABLE",
        notification_method="webhook",
        success=True
    )
    db_session.add(alert)
    
    db_session.commit()
    
    # Verify data exists
    assert db_session.query(Credential).filter(Credential.vm_id == vm_id).count() == 1
    assert db_session.query(PingResult).filter(PingResult.vm_id == vm_id).count() == 1
    assert db_session.query(Metric).filter(Metric.vm_id == vm_id).count() == 1
    assert db_session.query(Alert).filter(Alert.vm_id == vm_id).count() == 1
    
    # Delete VM
    vm_registry_service.delete_vm(test_user.id, vm_id)
    
    # Verify all related data is deleted
    assert db_session.query(Credential).filter(Credential.vm_id == vm_id).count() == 0
    assert db_session.query(PingResult).filter(PingResult.vm_id == vm_id).count() == 0
    assert db_session.query(Metric).filter(Metric.vm_id == vm_id).count() == 0
    assert db_session.query(Alert).filter(Alert.vm_id == vm_id).count() == 0


def test_delete_vm_unauthorized(vm_registry_service, test_user, test_user2, valid_ssh_key):
    """Test that users cannot delete other users' VMs (Requirement 3.3)."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm = vm_registry_service.create_vm(test_user.id, vm_data)
    
    with pytest.raises(UnauthorizedAccessError):
        vm_registry_service.delete_vm(test_user2.id, vm.id)


# Test check_duplicate

def test_check_duplicate_true(vm_registry_service, test_user, valid_ssh_key):
    """Test duplicate detection returns True for existing VM."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    vm_registry_service.create_vm(test_user.id, vm_data)
    
    is_duplicate = vm_registry_service.check_duplicate(test_user.id, "192.168.1.100", 22)
    assert is_duplicate is True


def test_check_duplicate_false(vm_registry_service, test_user):
    """Test duplicate detection returns False for non-existing VM."""
    is_duplicate = vm_registry_service.check_duplicate(test_user.id, "192.168.1.100", 22)
    assert is_duplicate is False


def test_check_duplicate_different_user(vm_registry_service, test_user, test_user2, valid_ssh_key):
    """Test duplicate detection is per-user."""
    vm_data = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    
    # User 1 creates VM
    vm_registry_service.create_vm(test_user.id, vm_data)
    
    # User 2 can create VM with same IP+port (different user)
    is_duplicate = vm_registry_service.check_duplicate(test_user2.id, "192.168.1.100", 22)
    assert is_duplicate is False


# Test list_vms_with_latest_metrics (optimized query)

def test_list_vms_with_latest_metrics_empty(vm_registry_service, test_user):
    """Test listing VMs with metrics when user has no VMs."""
    result = vm_registry_service.list_vms_with_latest_metrics(test_user.id)
    
    assert result == []


def test_list_vms_with_latest_metrics_no_monitoring_data(vm_registry_service, test_user, valid_ssh_key):
    """Test listing VMs with metrics when VMs have no monitoring data."""
    # Create 2 VMs
    for i in range(2):
        vm_data = VMCreateSchema(
            ip_address=f"192.168.1.{100+i}",
            hostname=f"vm-{i}",
            ssh_port=22,
            ssh_username="root",
            ssh_private_key=valid_ssh_key
        )
        vm_registry_service.create_vm(test_user.id, vm_data)
    
    result = vm_registry_service.list_vms_with_latest_metrics(test_user.id)
    
    assert len(result) == 2
    assert result[0]["vm"].hostname == "vm-0"
    assert result[0]["latest_metric"] is None
    assert result[0]["latest_ping"] is None
    assert result[1]["vm"].hostname == "vm-1"
    assert result[1]["latest_metric"] is None
    assert result[1]["latest_ping"] is None


def test_list_vms_with_latest_metrics_with_data(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test listing VMs with metrics when VMs have monitoring data."""
    # Create 2 VMs
    vms = []
    for i in range(2):
        vm_data = VMCreateSchema(
            ip_address=f"192.168.1.{100+i}",
            hostname=f"vm-{i}",
            ssh_port=22,
            ssh_username="root",
            ssh_private_key=valid_ssh_key
        )
        vm = vm_registry_service.create_vm(test_user.id, vm_data)
        vms.append(vm)
    
    # Add metrics for first VM (multiple records, should get latest)
    metric1_old = Metric(
        vm_id=vms[0].id,
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        cpu_usage_percent=30.0,
        ram_used_mb=1024,
        ram_total_mb=4096,
        disk_used_gb=25.0,
        disk_total_gb=100.0,
        disk_usage_percent=25.0,
        collection_success=True
    )
    db_session.add(metric1_old)
    
    metric1_new = Metric(
        vm_id=vms[0].id,
        timestamp=datetime(2024, 1, 1, 11, 0, 0),
        cpu_usage_percent=50.0,
        ram_used_mb=2048,
        ram_total_mb=4096,
        disk_used_gb=50.0,
        disk_total_gb=100.0,
        disk_usage_percent=50.0,
        collection_success=True
    )
    db_session.add(metric1_new)
    
    # Add ping results for first VM (multiple records, should get latest)
    ping1_old = PingResult(
        vm_id=vms[0].id,
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        success=True,
        response_time_ms=10.5,
        icmp_success=True,
        tcp_success=True
    )
    db_session.add(ping1_old)
    
    ping1_new = PingResult(
        vm_id=vms[0].id,
        timestamp=datetime(2024, 1, 1, 11, 0, 0),
        success=False,
        response_time_ms=None,
        error_type="TIMEOUT",
        icmp_success=False,
        tcp_success=False
    )
    db_session.add(ping1_new)
    
    # Add only metric for second VM (no ping)
    metric2 = Metric(
        vm_id=vms[1].id,
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        cpu_usage_percent=20.0,
        ram_used_mb=512,
        ram_total_mb=2048,
        disk_used_gb=10.0,
        disk_total_gb=50.0,
        disk_usage_percent=20.0,
        collection_success=True
    )
    db_session.add(metric2)
    
    db_session.commit()
    
    # Get VMs with latest metrics
    result = vm_registry_service.list_vms_with_latest_metrics(test_user.id)
    
    assert len(result) == 2
    
    # First VM should have latest metric and ping
    assert result[0]["vm"].hostname == "vm-0"
    assert result[0]["latest_metric"] is not None
    assert result[0]["latest_metric"].cpu_usage_percent == 50.0  # Latest metric
    assert result[0]["latest_metric"].timestamp == datetime(2024, 1, 1, 11, 0, 0)
    assert result[0]["latest_ping"] is not None
    assert result[0]["latest_ping"].success is False  # Latest ping
    assert result[0]["latest_ping"].timestamp == datetime(2024, 1, 1, 11, 0, 0)
    
    # Second VM should have metric but no ping
    assert result[1]["vm"].hostname == "vm-1"
    assert result[1]["latest_metric"] is not None
    assert result[1]["latest_metric"].cpu_usage_percent == 20.0
    assert result[1]["latest_ping"] is None


def test_list_vms_with_latest_metrics_user_isolation(vm_registry_service, test_user, test_user2, valid_ssh_key, db_session):
    """Test that list_vms_with_latest_metrics respects user isolation."""
    # User 1 creates VM with metrics
    vm_data1 = VMCreateSchema(
        ip_address="192.168.1.100",
        hostname="user1-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm1 = vm_registry_service.create_vm(test_user.id, vm_data1)
    
    metric1 = Metric(
        vm_id=vm1.id,
        cpu_usage_percent=50.0,
        ram_used_mb=2048,
        ram_total_mb=4096,
        disk_used_gb=50.0,
        disk_total_gb=100.0,
        disk_usage_percent=50.0,
        collection_success=True
    )
    db_session.add(metric1)
    
    # User 2 creates VM with metrics
    vm_data2 = VMCreateSchema(
        ip_address="192.168.1.101",
        hostname="user2-vm",
        ssh_port=22,
        ssh_username="root",
        ssh_private_key=valid_ssh_key
    )
    vm2 = vm_registry_service.create_vm(test_user2.id, vm_data2)
    
    metric2 = Metric(
        vm_id=vm2.id,
        cpu_usage_percent=30.0,
        ram_used_mb=1024,
        ram_total_mb=2048,
        disk_used_gb=25.0,
        disk_total_gb=50.0,
        disk_usage_percent=50.0,
        collection_success=True
    )
    db_session.add(metric2)
    
    db_session.commit()
    
    # User 1 should only see their VM
    result1 = vm_registry_service.list_vms_with_latest_metrics(test_user.id)
    assert len(result1) == 1
    assert result1[0]["vm"].hostname == "user1-vm"
    assert result1[0]["latest_metric"].cpu_usage_percent == 50.0
    
    # User 2 should only see their VM
    result2 = vm_registry_service.list_vms_with_latest_metrics(test_user2.id)
    assert len(result2) == 1
    assert result2[0]["vm"].hostname == "user2-vm"
    assert result2[0]["latest_metric"].cpu_usage_percent == 30.0


def test_list_vms_with_latest_metrics_performance(vm_registry_service, test_user, valid_ssh_key, db_session):
    """Test that list_vms_with_latest_metrics uses optimized query (single query instead of N+1)."""
    import time
    from sqlalchemy import event
    
    # Track query count
    query_count = {"count": 0}
    
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_count["count"] += 1
    
    # Register event listener to count queries
    event.listen(db_session.bind, "after_cursor_execute", receive_after_cursor_execute)
    
    try:
        # Create 10 VMs with metrics and pings
        for i in range(10):
            vm_data = VMCreateSchema(
                ip_address=f"192.168.1.{100+i}",
                hostname=f"vm-{i}",
                ssh_port=22,
                ssh_username="root",
                ssh_private_key=valid_ssh_key
            )
            vm = vm_registry_service.create_vm(test_user.id, vm_data)
            
            # Add metric
            metric = Metric(
                vm_id=vm.id,
                cpu_usage_percent=float(i * 10),
                ram_used_mb=1024,
                ram_total_mb=4096,
                disk_used_gb=25.0,
                disk_total_gb=100.0,
                disk_usage_percent=25.0,
                collection_success=True
            )
            db_session.add(metric)
            
            # Add ping
            ping = PingResult(
                vm_id=vm.id,
                success=True,
                response_time_ms=10.5,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping)
        
        db_session.commit()
        
        # Reset query count
        query_count["count"] = 0
        
        # Execute list_vms_with_latest_metrics
        start_time = time.time()
        result = vm_registry_service.list_vms_with_latest_metrics(test_user.id)
        end_time = time.time()
        
        # Verify results
        assert len(result) == 10
        
        # Verify query count - should be 1 query (optimized) instead of 21 (N+1)
        # The optimized query uses subqueries and JOINs to fetch everything in one go
        assert query_count["count"] == 1, f"Expected 1 query, got {query_count['count']}"
        
        # Verify performance - should be fast even with 10 VMs
        execution_time = (end_time - start_time) * 1000  # Convert to ms
        assert execution_time < 100, f"Query took {execution_time:.2f}ms, expected < 100ms"
        
    finally:
        # Remove event listener
        event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute)
