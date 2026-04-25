"""
Property-based tests for user isolation enforcement.

Tests Property 5: User Isolation Enforcement
Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import pytest
from hypothesis import given, strategies as st, assume
from sqlalchemy.orm import Session
from vmledger.services.vm_registry_service import VMRegistryService
from vmledger.models.vm import VM
from vmledger.models.user import User
from vmledger.exceptions import UnauthorizedError, VMNotFoundError


# Strategy for generating user IDs
user_ids = st.integers(min_value=1, max_value=1000)

# Strategy for generating VM IDs
vm_ids = st.integers(min_value=1, max_value=10000)


@given(
    owner_id=user_ids,
    other_user_id=user_ids,
    vm_id=vm_ids
)
def test_property_user_cannot_access_other_users_vms(
    owner_id, other_user_id, vm_id, mock_db_session
):
    """
    Property 5: User Isolation Enforcement
    
    Property: A user should never be able to access (read, update, delete) 
    another user's VMs.
    
    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    # Arrange
    assume(owner_id != other_user_id)  # Different users
    
    vm_service = VMRegistryService(mock_db_session)
    
    # Create a mock VM owned by owner_id
    mock_vm = VM(
        id=vm_id,
        user_id=owner_id,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes="Test VM"
    )
    
    # Mock the database query to return this VM
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act & Assert - Try to access as other_user_id
    with pytest.raises((UnauthorizedError, VMNotFoundError)):
        vm_service.get_vm(vm_id, other_user_id)


@given(
    user_id=user_ids,
    vm_count=st.integers(min_value=0, max_value=100)
)
def test_property_list_vms_returns_only_user_vms(user_id, vm_count, mock_db_session):
    """
    Property 5: User Isolation Enforcement (List Operation)
    
    Property: When listing VMs, a user should only see their own VMs, never VMs
    belonging to other users.
    
    Validates: Requirements 3.2 - List only user's own VMs
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Create mock VMs for this user
    user_vms = [
        VM(
            id=i,
            user_id=user_id,
            hostname=f"vm-{i}",
            ip_address=f"192.168.1.{i % 255}",
            ssh_port=22,
            tags=["test"],
            deployment_notes=""
        )
        for i in range(vm_count)
    ]
    
    # Mock the database query
    mock_db_session.query.return_value.filter.return_value.all.return_value = user_vms
    
    # Act
    result = vm_service.list_vms(user_id)
    
    # Assert
    assert len(result) == vm_count
    for vm in result:
        assert vm.user_id == user_id, "VM list contains VMs from other users!"


@given(
    owner_id=user_ids,
    other_user_id=user_ids,
    vm_id=vm_ids,
    new_hostname=st.text(min_size=1, max_size=255, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
    ))
)
def test_property_user_cannot_update_other_users_vms(
    owner_id, other_user_id, vm_id, new_hostname, mock_db_session
):
    """
    Property 5: User Isolation Enforcement (Update Operation)
    
    Property: A user should never be able to update another user's VMs.
    
    Validates: Requirements 3.3 - Update only user's own VMs
    """
    # Arrange
    assume(owner_id != other_user_id)
    assume(len(new_hostname) > 0)
    
    vm_service = VMRegistryService(mock_db_session)
    
    # Create a mock VM owned by owner_id
    mock_vm = VM(
        id=vm_id,
        user_id=owner_id,
        hostname="original-hostname",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act & Assert - Try to update as other_user_id
    with pytest.raises((UnauthorizedError, VMNotFoundError)):
        vm_service.update_vm(
            vm_id=vm_id,
            user_id=other_user_id,
            hostname=new_hostname
        )


@given(
    owner_id=user_ids,
    other_user_id=user_ids,
    vm_id=vm_ids
)
def test_property_user_cannot_delete_other_users_vms(
    owner_id, other_user_id, vm_id, mock_db_session
):
    """
    Property 5: User Isolation Enforcement (Delete Operation)
    
    Property: A user should never be able to delete another user's VMs.
    
    Validates: Requirements 3.4 - Delete only user's own VMs
    """
    # Arrange
    assume(owner_id != other_user_id)
    
    vm_service = VMRegistryService(mock_db_session)
    
    # Create a mock VM owned by owner_id
    mock_vm = VM(
        id=vm_id,
        user_id=owner_id,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act & Assert - Try to delete as other_user_id
    with pytest.raises((UnauthorizedError, VMNotFoundError)):
        vm_service.delete_vm(vm_id, other_user_id)


@given(
    user_id=user_ids,
    vm_id=vm_ids
)
def test_property_user_can_access_own_vms(user_id, vm_id, mock_db_session):
    """
    Property 5: User Isolation Enforcement (Positive Case)
    
    Property: A user should always be able to access their own VMs.
    
    Validates: Requirements 3.1 - View only user's own VMs
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Create a mock VM owned by user_id
    mock_vm = VM(
        id=vm_id,
        user_id=user_id,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes="Test VM"
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    result = vm_service.get_vm(vm_id, user_id)
    
    # Assert
    assert result is not None
    assert result.id == vm_id
    assert result.user_id == user_id


@given(
    user1_id=user_ids,
    user2_id=user_ids,
    ip_address=st.text(min_size=7, max_size=15, alphabet=st.characters(
        whitelist_categories=("Nd",), whitelist_characters="."
    )),
    ssh_port=st.integers(min_value=1, max_value=65535)
)
def test_property_duplicate_check_respects_user_isolation(
    user1_id, user2_id, ip_address, ssh_port, mock_db_session
):
    """
    Property 5: User Isolation Enforcement (Duplicate Check)
    
    Property: Duplicate VM check (same IP + port) should only apply within
    a single user's VMs, not across users.
    
    Validates: Requirements 3.5 - User isolation in all operations
    """
    # Arrange
    assume(user1_id != user2_id)
    
    vm_service = VMRegistryService(mock_db_session)
    
    # User 1 already has a VM with this IP + port
    existing_vm = VM(
        id=1,
        user_id=user1_id,
        hostname="user1-vm",
        ip_address=ip_address,
        ssh_port=ssh_port,
        tags=["test"],
        deployment_notes=""
    )
    
    # Mock: User 1 has the VM, User 2 doesn't
    def mock_filter_side_effect(*args, **kwargs):
        mock_result = mock_db_session.query.return_value.filter.return_value
        # Return existing VM only for user1
        if hasattr(args[0], 'right') and args[0].right.value == user1_id:
            mock_result.first.return_value = existing_vm
        else:
            mock_result.first.return_value = None
        return mock_result
    
    mock_db_session.query.return_value.filter.side_effect = mock_filter_side_effect
    
    # Act & Assert
    # User 1 should not be able to create duplicate
    is_duplicate_user1 = vm_service.check_duplicate(ip_address, ssh_port, user1_id)
    assert is_duplicate_user1 is True, "Should detect duplicate for user1"
    
    # User 2 should be able to create VM with same IP + port
    is_duplicate_user2 = vm_service.check_duplicate(ip_address, ssh_port, user2_id)
    assert is_duplicate_user2 is False, "Should NOT detect duplicate for user2 (different user)"
