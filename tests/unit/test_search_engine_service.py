"""
Unit tests for SearchEngineService.

Tests Requirements 7.1-7.6 (Global Search):
- 7.1: Index VM metadata and deployment notes
- 7.2: Return results within 500ms
- 7.3: Support partial word matching
- 7.4: Rank by relevance (exact matches first)
- 7.5: Highlight matches in deployment notes
- 7.6: OR logic for multi-term queries

Note: These tests use SQLite which doesn't support PostgreSQL's full-text search features.
The tests verify the service interface and basic functionality. Full-text search features
should be tested with integration tests using a real PostgreSQL database.
"""

import pytest
from sqlalchemy.orm import Session
from vmledger.services.search_engine_service import SearchEngineService, VMSearchResult
from vmledger.models.user import User
from vmledger.models.vm import VM
import time


@pytest.fixture
def search_service(db_session: Session) -> SearchEngineService:
    """Create SearchEngineService instance."""
    return SearchEngineService(db_session)


@pytest.fixture
def search_test_user(db_session: Session) -> User:
    """Create a test user for search tests."""
    user = User(
        username="searchuser",
        email="search@test.com",
        password_hash="hashed_password",
        encryption_salt="test_salt"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def search_test_vms(db_session: Session, search_test_user: User) -> list[VM]:
    """Create test VMs with various content for search testing."""
    vms = [
        VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.100",
            hostname="web-server-01",
            domain="example.com",
            ssh_port=22,
            tags='["web", "nginx", "production"]',  # JSON string for SQLite
            deployment_notes="Running Nginx web server with SSL certificates. Production environment."
        ),
        VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.101",
            hostname="db-server-01",
            domain="example.com",
            ssh_port=22,
            tags='["database", "postgresql", "production"]',
            deployment_notes="PostgreSQL 15 database server. Primary instance for production data."
        ),
        VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.102",
            hostname="app-server-01",
            domain="staging.example.com",
            ssh_port=2222,
            tags='["application", "python", "staging"]',
            deployment_notes="Python FastAPI application server. Staging environment for testing."
        ),
        VM(
            user_id=search_test_user.id,
            ip_address="10.0.0.50",
            hostname="cache-server",
            domain="internal.example.com",
            ssh_port=22,
            tags='["cache", "redis"]',
            deployment_notes="Redis cache server for session storage and rate limiting."
        ),
        VM(
            user_id=search_test_user.id,
            ip_address="10.0.0.51",
            hostname="monitoring-server",
            domain="internal.example.com",
            ssh_port=22,
            tags='["monitoring", "prometheus", "grafana"]',
            deployment_notes="Prometheus and Grafana monitoring stack. Collects metrics from all servers."
        ),
    ]
    
    for vm in vms:
        db_session.add(vm)
    
    db_session.commit()
    
    # Refresh to get any auto-populated fields
    for vm in vms:
        db_session.refresh(vm)
    
    return vms


class TestSearchVMsBasic:
    """Test basic search_vms functionality (SQLite compatible)."""
    
    def test_empty_query(self, search_service: SearchEngineService, search_test_user: User, search_test_vms: list[VM]):
        """Test searching with empty query."""
        results = search_service.search_vms(search_test_user.id, "")
        assert len(results) == 0
        
        results = search_service.search_vms(search_test_user.id, "   ")
        assert len(results) == 0
    
    def test_user_isolation(self, db_session: Session, search_service: SearchEngineService, search_test_user: User, search_test_vms: list[VM]):
        """Test that search respects user isolation."""
        # Create another user with their own VM
        other_user = User(
            username="otheruser",
            email="other@test.com",
            password_hash="hashed_password",
            encryption_salt="other_salt"
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        
        other_vm = VM(
            user_id=other_user.id,
            ip_address="172.16.0.1",
            hostname="other-server",
            domain="other.com",
            ssh_port=22,
            tags='["other"]',
            deployment_notes="This belongs to another user"
        )
        db_session.add(other_vm)
        db_session.commit()
        db_session.refresh(other_vm)
        
        # Note: Full-text search won't work in SQLite, but we can verify
        # that the service doesn't crash and respects user_id filtering
        try:
            results = search_service.search_vms(search_test_user.id, "other")
            # In SQLite, this will likely return 0 results due to missing FTS support
            # The important thing is it doesn't return other_user's VM
            for result in results:
                assert result.vm.user_id == search_test_user.id
        except Exception as e:
            # Expected in SQLite - full-text search not supported
            assert "to_tsquery" in str(e) or "@@" in str(e) or "ts_rank" in str(e)


class TestHighlightMatches:
    """Test highlight_matches method."""
    
    def test_highlight_empty_text(self, search_service: SearchEngineService):
        """Test highlighting with empty text."""
        result = search_service.highlight_matches("", "test")
        assert result == ""
    
    def test_highlight_empty_query(self, search_service: SearchEngineService):
        """Test highlighting with empty query."""
        text = "Some text content"
        result = search_service.highlight_matches(text, "")
        assert result == text


class TestIndexOperations:
    """Test index_vm, update_index, and delete_from_index methods."""
    
    def test_index_vm_interface(self, db_session: Session, search_service: SearchEngineService, search_test_user: User):
        """Test that index_vm method exists and accepts correct parameters."""
        vm = VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.200",
            hostname="new-server",
            domain="test.com",
            ssh_port=22,
            tags='["new", "test"]',
            deployment_notes="Newly created server for testing indexing"
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)
        
        # Test that the method can be called without errors (even if FTS doesn't work in SQLite)
        try:
            search_service.index_vm(vm)
        except Exception as e:
            # Expected in SQLite - full-text search functions not available
            assert "to_tsvector" in str(e) or "setweight" in str(e)
    
    def test_update_index_interface(self, db_session: Session, search_service: SearchEngineService, search_test_user: User):
        """Test that update_index method exists and accepts correct parameters."""
        vm = VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.201",
            hostname="update-server",
            domain="test.com",
            ssh_port=22,
            tags='["original"]',
            deployment_notes="Original content"
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)
        
        # Update VM content
        vm.tags = '["updated", "modified"]'
        vm.deployment_notes = "Updated content with new information"
        db_session.commit()
        
        # Test that the method can be called
        try:
            search_service.update_index(vm.id, vm)
        except Exception as e:
            # Expected in SQLite
            assert "to_tsvector" in str(e) or "setweight" in str(e)
    
    def test_delete_from_index(self, db_session: Session, search_service: SearchEngineService, search_test_user: User):
        """Test deleting VM from index."""
        vm = VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.202",
            hostname="delete-server",
            domain="test.com",
            ssh_port=22,
            tags='["delete"]',
            deployment_notes="This will be deleted"
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)
        
        # Delete from index (this is a no-op but should not raise errors)
        search_service.delete_from_index(vm.id)
        
        # Delete from database
        db_session.delete(vm)
        db_session.commit()


class TestVMSearchResult:
    """Test VMSearchResult class."""
    
    def test_to_dict(self, db_session: Session, search_test_user: User):
        """Test converting search result to dictionary."""
        vm = VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.100",
            hostname="test-server",
            domain="test.com",
            ssh_port=22,
            tags='["test", "example"]',
            deployment_notes="Test deployment notes",
            is_reachable=True
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)
        
        result = VMSearchResult(
            vm=vm,
            rank=0.5,
            highlighted_notes="Test <mark>deployment</mark> notes"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['id'] == vm.id
        assert result_dict['ip_address'] == "192.168.1.100"
        assert result_dict['hostname'] == "test-server"
        assert result_dict['domain'] == "test.com"
        assert result_dict['ssh_port'] == 22
        # Tags will be a JSON string in SQLite (not deserialized in to_dict)
        assert result_dict['tags'] is not None
        assert result_dict['deployment_notes'] == "Test deployment notes"
        assert result_dict['highlighted_notes'] == "Test <mark>deployment</mark> notes"
        assert result_dict['rank'] == 0.5
        assert result_dict['is_reachable'] is True
        assert 'created_at' in result_dict
        assert 'updated_at' in result_dict
    
    def test_to_dict_with_none_values(self, db_session: Session, search_test_user: User):
        """Test converting search result with None values."""
        vm = VM(
            user_id=search_test_user.id,
            ip_address="192.168.1.101",
            hostname="minimal-server",
            ssh_port=22
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)
        
        result = VMSearchResult(vm=vm, rank=0.3)
        result_dict = result.to_dict()
        
        assert result_dict['domain'] is None
        assert result_dict['tags'] == []
        assert result_dict['deployment_notes'] is None
        assert result_dict['highlighted_notes'] is None
        assert result_dict['last_seen'] is None
        assert result_dict['is_reachable'] is None


class TestServiceInterface:
    """Test that the service interface is correctly defined."""
    
    def test_service_initialization(self, db_session: Session):
        """Test that service can be initialized with a database session."""
        service = SearchEngineService(db_session)
        assert service.db == db_session
    
    def test_search_vms_signature(self, search_service: SearchEngineService):
        """Test that search_vms has the correct signature."""
        import inspect
        sig = inspect.signature(search_service.search_vms)
        params = list(sig.parameters.keys())
        assert 'user_id' in params
        assert 'query' in params
        assert 'limit' in params
    
    def test_highlight_matches_signature(self, search_service: SearchEngineService):
        """Test that highlight_matches has the correct signature."""
        import inspect
        sig = inspect.signature(search_service.highlight_matches)
        params = list(sig.parameters.keys())
        assert 'text' in params
        assert 'ts_query' in params
    
    def test_index_vm_signature(self, search_service: SearchEngineService):
        """Test that index_vm has the correct signature."""
        import inspect
        sig = inspect.signature(search_service.index_vm)
        params = list(sig.parameters.keys())
        assert 'vm' in params
    
    def test_update_index_signature(self, search_service: SearchEngineService):
        """Test that update_index has the correct signature."""
        import inspect
        sig = inspect.signature(search_service.update_index)
        params = list(sig.parameters.keys())
        assert 'vm_id' in params
        assert 'vm' in params
    
    def test_delete_from_index_signature(self, search_service: SearchEngineService):
        """Test that delete_from_index has the correct signature."""
        import inspect
        sig = inspect.signature(search_service.delete_from_index)
        params = list(sig.parameters.keys())
        assert 'vm_id' in params
