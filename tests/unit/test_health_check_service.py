"""
Unit tests for HealthCheckService.

Tests the health check service with mocked network operations.
Requirements: 4.1-4.6
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from vmledger.services.health_check_service import (
    HealthCheckService,
    HealthCheckServiceError,
    PingResultData,
)
from vmledger.models.vm import VM
from vmledger.models.ping_result import PingResult


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return db


@pytest.fixture
def health_check_service(mock_db):
    """Create a HealthCheckService instance with mock database."""
    return HealthCheckService(mock_db)


@pytest.fixture
def test_vm():
    """Create a test VM object."""
    vm = VM(
        id=1,
        user_id=1,
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        is_reachable=None
    )
    return vm


class TestCheckICMPPing:
    """Tests for check_icmp_ping method."""
    
    @patch('vmledger.services.health_check_service.ping')
    def test_successful_icmp_ping(self, mock_ping, health_check_service):
        """Test successful ICMP ping returns response time."""
        # Mock ping3 to return response time in milliseconds
        mock_ping.return_value = 15.5
        
        result = health_check_service.check_icmp_ping("192.168.1.100", timeout=5)
        
        assert result == 15.5
        mock_ping.assert_called_once_with("192.168.1.100", timeout=5, unit='ms')
    
    @patch('vmledger.services.health_check_service.ping')
    def test_failed_icmp_ping_returns_none(self, mock_ping, health_check_service):
        """Test failed ICMP ping returns None."""
        # Mock ping3 to return None (failure)
        mock_ping.return_value = None
        
        result = health_check_service.check_icmp_ping("192.168.1.100", timeout=5)
        
        assert result is None
    
    @patch('vmledger.services.health_check_service.ping')
    def test_icmp_ping_exception_returns_none(self, mock_ping, health_check_service):
        """Test ICMP ping exception returns None."""
        # Mock ping3 to raise exception
        mock_ping.side_effect = Exception("Network error")
        
        result = health_check_service.check_icmp_ping("192.168.1.100", timeout=5)
        
        assert result is None


class TestCheckTCPPort:
    """Tests for check_tcp_port method."""
    
    @patch('vmledger.services.health_check_service.socket.socket')
    def test_successful_tcp_connection(self, mock_socket_class, health_check_service):
        """Test successful TCP connection returns True."""
        # Mock socket to return success (0)
        mock_socket = Mock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_socket
        
        result = health_check_service.check_tcp_port("192.168.1.100", 22, timeout=5)
        
        assert result is True
        mock_socket.settimeout.assert_called_once_with(5)
        mock_socket.connect_ex.assert_called_once_with(("192.168.1.100", 22))
        mock_socket.close.assert_called_once()
    
    @patch('vmledger.services.health_check_service.socket.socket')
    def test_failed_tcp_connection(self, mock_socket_class, health_check_service):
        """Test failed TCP connection returns False."""
        # Mock socket to return error code
        mock_socket = Mock()
        mock_socket.connect_ex.return_value = 111  # Connection refused
        mock_socket_class.return_value = mock_socket
        
        result = health_check_service.check_tcp_port("192.168.1.100", 22, timeout=5)
        
        assert result is False
    
    @patch('vmledger.services.health_check_service.socket.socket')
    def test_tcp_connection_timeout(self, mock_socket_class, health_check_service):
        """Test TCP connection timeout returns False."""
        # Mock socket to raise timeout
        mock_socket = Mock()
        mock_socket.connect_ex.side_effect = TimeoutError("Connection timeout")
        mock_socket_class.return_value = mock_socket
        
        result = health_check_service.check_tcp_port("192.168.1.100", 22, timeout=5)
        
        assert result is False


class TestExecutePing:
    """Tests for execute_ping method."""
    
    def test_successful_ping_both_checks_pass(self, health_check_service, test_vm):
        """Test successful ping when both ICMP and TCP succeed."""
        with patch.object(health_check_service, 'check_icmp_ping', return_value=15.5), \
             patch.object(health_check_service, 'check_tcp_port', return_value=True):
            
            result = health_check_service.execute_ping(test_vm)
            
            assert result.success is True
            assert result.response_time_ms == 15.5
            assert result.error_type is None
            assert result.icmp_success is True
            assert result.tcp_success is True
    
    def test_failed_ping_both_checks_fail(self, health_check_service, test_vm):
        """Test failed ping when both ICMP and TCP fail."""
        with patch.object(health_check_service, 'check_icmp_ping', return_value=None), \
             patch.object(health_check_service, 'check_tcp_port', return_value=False):
            
            result = health_check_service.execute_ping(test_vm)
            
            assert result.success is False
            assert result.response_time_ms is None
            assert result.error_type == HealthCheckService.ERROR_TIMEOUT
            assert result.icmp_success is False
            assert result.tcp_success is False
    
    def test_failed_ping_tcp_refused(self, health_check_service, test_vm):
        """Test failed ping when ICMP succeeds but TCP fails (port refused)."""
        with patch.object(health_check_service, 'check_icmp_ping', return_value=15.5), \
             patch.object(health_check_service, 'check_tcp_port', return_value=False):
            
            result = health_check_service.execute_ping(test_vm)
            
            assert result.success is False
            assert result.response_time_ms == 15.5
            assert result.error_type == HealthCheckService.ERROR_TCP_REFUSED
            assert result.icmp_success is True
            assert result.tcp_success is False
    
    def test_failed_ping_icmp_timeout(self, health_check_service, test_vm):
        """Test failed ping when TCP succeeds but ICMP fails."""
        with patch.object(health_check_service, 'check_icmp_ping', return_value=None), \
             patch.object(health_check_service, 'check_tcp_port', return_value=True):
            
            result = health_check_service.execute_ping(test_vm)
            
            assert result.success is False
            assert result.response_time_ms is None
            assert result.error_type == HealthCheckService.ERROR_ICMP_TIMEOUT
            assert result.icmp_success is False
            assert result.tcp_success is True


class TestStorePingResult:
    """Tests for store_ping_result method."""
    
    def test_store_successful_ping_result(self, health_check_service, mock_db, test_vm):
        """Test storing successful ping result updates VM status."""
        # Setup mock VM
        mock_db.query.return_value.filter.return_value.first.return_value = test_vm
        
        result_data = PingResultData(
            success=True,
            response_time_ms=15.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        
        health_check_service.store_ping_result(test_vm.id, result_data)
        
        # Verify ping result was added
        mock_db.add.assert_called_once()
        added_result = mock_db.add.call_args[0][0]
        assert isinstance(added_result, PingResult)
        assert added_result.vm_id == test_vm.id
        assert added_result.success is True
        assert added_result.response_time_ms == 15.5
        assert added_result.error_type is None
        
        # Verify VM status was updated
        assert test_vm.is_reachable is True
        assert test_vm.last_seen is not None
        
        # Verify commit was called
        mock_db.commit.assert_called_once()
    
    def test_store_failed_ping_result(self, health_check_service, mock_db, test_vm):
        """Test storing failed ping result updates VM status."""
        # Setup mock VM
        mock_db.query.return_value.filter.return_value.first.return_value = test_vm
        
        result_data = PingResultData(
            success=False,
            response_time_ms=None,
            error_type=HealthCheckService.ERROR_TIMEOUT,
            icmp_success=False,
            tcp_success=False
        )
        
        health_check_service.store_ping_result(test_vm.id, result_data)
        
        # Verify ping result was added
        mock_db.add.assert_called_once()
        added_result = mock_db.add.call_args[0][0]
        assert added_result.success is False
        assert added_result.error_type == HealthCheckService.ERROR_TIMEOUT
        
        # Verify VM status was updated
        assert test_vm.is_reachable is False
        
        # Verify commit was called
        mock_db.commit.assert_called_once()
    
    def test_store_ping_result_database_error(self, health_check_service, mock_db):
        """Test storing ping result handles database errors."""
        # Mock database to raise exception
        mock_db.add.side_effect = Exception("Database error")
        
        result_data = PingResultData(
            success=True,
            response_time_ms=15.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        
        with pytest.raises(HealthCheckServiceError):
            health_check_service.store_ping_result(1, result_data)
        
        # Verify rollback was called
        mock_db.rollback.assert_called_once()


class TestGetPingHistory:
    """Tests for get_ping_history method."""
    
    def test_get_ping_history_returns_results(self, health_check_service, mock_db):
        """Test retrieving ping history returns results."""
        # Create mock ping results
        mock_results = [
            PingResult(
                id=1,
                vm_id=1,
                timestamp=datetime.utcnow(),
                success=True,
                response_time_ms=15.5,
                error_type=None,
                icmp_success=True,
                tcp_success=True
            ),
            PingResult(
                id=2,
                vm_id=1,
                timestamp=datetime.utcnow(),
                success=False,
                response_time_ms=None,
                error_type=HealthCheckService.ERROR_TIMEOUT,
                icmp_success=False,
                tcp_success=False
            )
        ]
        
        # Setup mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_db.query.return_value = mock_query
        
        results = health_check_service.get_ping_history(1, limit=100)
        
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        
        # Verify query was constructed correctly
        mock_db.query.assert_called_once_with(PingResult)
        mock_query.limit.assert_called_once_with(100)
    
    def test_get_ping_history_with_custom_limit(self, health_check_service, mock_db):
        """Test retrieving ping history with custom limit."""
        # Setup mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        health_check_service.get_ping_history(1, limit=50)
        
        # Verify limit was applied
        mock_query.limit.assert_called_once_with(50)
    
    def test_get_ping_history_database_error(self, health_check_service, mock_db):
        """Test retrieving ping history handles database errors."""
        # Mock database to raise exception
        mock_db.query.side_effect = Exception("Database error")
        
        with pytest.raises(HealthCheckServiceError):
            health_check_service.get_ping_history(1)


class TestPingResultData:
    """Tests for PingResultData class."""
    
    def test_ping_result_data_success(self):
        """Test creating successful PingResultData."""
        result = PingResultData(
            success=True,
            response_time_ms=15.5,
            error_type=None,
            icmp_success=True,
            tcp_success=True
        )
        
        assert result.success is True
        assert result.response_time_ms == 15.5
        assert result.error_type is None
        assert result.icmp_success is True
        assert result.tcp_success is True
    
    def test_ping_result_data_failure(self):
        """Test creating failed PingResultData."""
        result = PingResultData(
            success=False,
            response_time_ms=None,
            error_type=HealthCheckService.ERROR_TIMEOUT,
            icmp_success=False,
            tcp_success=False
        )
        
        assert result.success is False
        assert result.response_time_ms is None
        assert result.error_type == HealthCheckService.ERROR_TIMEOUT
        assert result.icmp_success is False
        assert result.tcp_success is False
