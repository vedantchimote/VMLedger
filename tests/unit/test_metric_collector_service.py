"""
Unit tests for MetricCollectorService.

Tests metric collection, OS detection, SSH connection management,
retry logic, and error handling.

Requirements: 5.1-5.7
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from io import StringIO

from vmledger.services.metric_collector_service import (
    MetricCollectorService,
    MetricData,
    SSHConnectionError,
    CommandExecutionError
)
from vmledger.models.vm import VM
from vmledger.models.credential import Credential
from vmledger.models.metric import Metric


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def metric_service(mock_db):
    """Create MetricCollectorService instance with mock database."""
    return MetricCollectorService(mock_db)


@pytest.fixture
def mock_vm():
    """Create mock VM object."""
    vm = Mock(spec=VM)
    vm.id = 1
    vm.user_id = 1
    vm.hostname = "test-vm"
    vm.ip_address = "192.168.1.100"
    vm.ssh_port = 22
    return vm


@pytest.fixture
def mock_credential():
    """Create mock credential object."""
    cred = Mock(spec=Credential)
    cred.vm_id = 1
    cred.auth_type = "ssh_key"
    cred.ssh_username = "root"
    cred.encrypted_credential = "encrypted_key_data"
    return cred


class TestOSDetection:
    """Test OS detection functionality."""
    
    def test_detect_linux(self, metric_service):
        """Test Linux OS detection."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("Linux\n", "", 0)
        ):
            os_type = metric_service.detect_os(mock_client)
            assert os_type == MetricCollectorService.OS_LINUX
    
    def test_detect_macos(self, metric_service):
        """Test macOS OS detection."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("Darwin\n", "", 0)
        ):
            os_type = metric_service.detect_os(mock_client)
            assert os_type == MetricCollectorService.OS_MACOS
    
    def test_detect_unknown_os(self, metric_service):
        """Test unknown OS detection."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("FreeBSD\n", "", 0)
        ):
            os_type = metric_service.detect_os(mock_client)
            assert os_type == MetricCollectorService.OS_UNKNOWN
    
    def test_detect_os_command_failure(self, metric_service):
        """Test OS detection when command fails."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("", "command not found", 1)
        ):
            os_type = metric_service.detect_os(mock_client)
            assert os_type == MetricCollectorService.OS_UNKNOWN


class TestCPUUsageCollection:
    """Test CPU usage collection."""
    
    def test_get_cpu_usage_linux(self, metric_service):
        """Test CPU usage collection on Linux."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("25.5", "", 0)
        ):
            cpu_usage = metric_service.get_cpu_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert cpu_usage == 25.5
    
    def test_get_cpu_usage_macos(self, metric_service):
        """Test CPU usage collection on macOS."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("15.3%", "", 0)
        ):
            cpu_usage = metric_service.get_cpu_usage(
                mock_client,
                MetricCollectorService.OS_MACOS
            )
            assert cpu_usage == 15.3
    
    def test_get_cpu_usage_with_comma(self, metric_service):
        """Test CPU usage parsing with comma decimal separator."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("12,7", "", 0)
        ):
            cpu_usage = metric_service.get_cpu_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert cpu_usage == 12.7
    
    def test_get_cpu_usage_command_failure(self, metric_service):
        """Test CPU usage when command fails."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("", "command failed", 1)
        ):
            cpu_usage = metric_service.get_cpu_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert cpu_usage is None
    
    def test_get_cpu_usage_invalid_output(self, metric_service):
        """Test CPU usage with invalid output."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("not_a_number", "", 0)
        ):
            cpu_usage = metric_service.get_cpu_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert cpu_usage is None


class TestMemoryUsageCollection:
    """Test memory usage collection."""
    
    def test_get_memory_usage_linux(self, metric_service):
        """Test memory usage collection on Linux."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("2048 4096", "", 0)
        ):
            ram_used, ram_total = metric_service.get_memory_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert ram_used == 2048
            assert ram_total == 4096
    
    def test_get_memory_usage_macos(self, metric_service):
        """Test memory usage collection on macOS."""
        mock_client = Mock()
        
        # Mock multiple command executions for macOS
        with patch.object(
            metric_service,
            '_execute_command',
            side_effect=[
                ("4096", "", 0),  # pagesize
                ("100000\n50000\n30000\n20000\n10000", "", 0),  # vm_stat
                ("8589934592", "", 0)  # sysctl hw.memsize
            ]
        ):
            ram_used, ram_total = metric_service.get_memory_usage(
                mock_client,
                MetricCollectorService.OS_MACOS
            )
            assert ram_total == 8192  # 8GB in MB
            assert ram_used is not None
            assert ram_used > 0
    
    def test_get_memory_usage_command_failure(self, metric_service):
        """Test memory usage when command fails."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("", "command failed", 1)
        ):
            ram_used, ram_total = metric_service.get_memory_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert ram_used is None
            assert ram_total is None
    
    def test_get_memory_usage_invalid_output(self, metric_service):
        """Test memory usage with invalid output."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("invalid data", "", 0)
        ):
            ram_used, ram_total = metric_service.get_memory_usage(
                mock_client,
                MetricCollectorService.OS_LINUX
            )
            assert ram_used is None
            assert ram_total is None


class TestDiskUsageCollection:
    """Test disk usage collection."""
    
    def test_get_disk_usage_gb(self, metric_service):
        """Test disk usage with GB units."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("50G 100G 50%", "", 0)
        ):
            disk_used, disk_total, disk_percent = metric_service.get_disk_usage(
                mock_client
            )
            assert disk_used == 50.0
            assert disk_total == 100.0
            assert disk_percent == 50.0
    
    def test_get_disk_usage_tb(self, metric_service):
        """Test disk usage with TB units."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("1.5T 2T 75%", "", 0)
        ):
            disk_used, disk_total, disk_percent = metric_service.get_disk_usage(
                mock_client
            )
            assert disk_used == 1536.0  # 1.5TB in GB
            assert disk_total == 2048.0  # 2TB in GB
            assert disk_percent == 75.0
    
    def test_get_disk_usage_mb(self, metric_service):
        """Test disk usage with MB units."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("512M 1024M 50%", "", 0)
        ):
            disk_used, disk_total, disk_percent = metric_service.get_disk_usage(
                mock_client
            )
            assert disk_used == pytest.approx(0.5, rel=0.01)  # 512MB in GB
            assert disk_total == 1.0  # 1024MB in GB
            assert disk_percent == 50.0
    
    def test_get_disk_usage_command_failure(self, metric_service):
        """Test disk usage when command fails."""
        mock_client = Mock()
        
        with patch.object(
            metric_service,
            '_execute_command',
            return_value=("", "command failed", 1)
        ):
            disk_used, disk_total, disk_percent = metric_service.get_disk_usage(
                mock_client
            )
            assert disk_used is None
            assert disk_total is None
            assert disk_percent is None


class TestDiskSizeParsing:
    """Test disk size parsing helper."""
    
    def test_parse_disk_size_gb(self, metric_service):
        """Test parsing GB sizes."""
        assert metric_service._parse_disk_size("100G") == 100.0
        assert metric_service._parse_disk_size("1.5G") == 1.5
    
    def test_parse_disk_size_tb(self, metric_service):
        """Test parsing TB sizes."""
        assert metric_service._parse_disk_size("1T") == 1024.0
        assert metric_service._parse_disk_size("2.5T") == 2560.0
    
    def test_parse_disk_size_mb(self, metric_service):
        """Test parsing MB sizes."""
        assert metric_service._parse_disk_size("512M") == pytest.approx(0.5, rel=0.01)
        assert metric_service._parse_disk_size("1024M") == 1.0
    
    def test_parse_disk_size_kb(self, metric_service):
        """Test parsing KB sizes."""
        result = metric_service._parse_disk_size("1024K")
        # 1024 KB = 1024 / (1024 * 1024) GB = 0.0009765625 GB
        assert result == pytest.approx(0.0009765625, rel=0.01)


class TestSSHConnection:
    """Test SSH connection management."""
    
    @patch('vmledger.services.metric_collector_service.paramiko.SSHClient')
    def test_create_ssh_client_with_key(self, mock_ssh_class, metric_service):
        """Test SSH connection with private key."""
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        
        # Mock RSA key loading
        with patch('vmledger.services.metric_collector_service.paramiko.RSAKey') as mock_rsa:
            mock_key = Mock()
            mock_rsa.from_private_key.return_value = mock_key
            
            client = metric_service._create_ssh_client(
                "192.168.1.100",
                22,
                "root",
                "ssh_key",
                "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
            )
            
            assert client == mock_client
            mock_client.connect.assert_called_once()
    
    @patch('vmledger.services.metric_collector_service.paramiko.SSHClient')
    def test_create_ssh_client_with_password(self, mock_ssh_class, metric_service):
        """Test SSH connection with password."""
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        
        client = metric_service._create_ssh_client(
            "192.168.1.100",
            22,
            "root",
            "password",
            "test_password"
        )
        
        assert client == mock_client
        mock_client.connect.assert_called_once()
        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs['password'] == "test_password"
    
    @patch('vmledger.services.metric_collector_service.paramiko.SSHClient')
    def test_create_ssh_client_auth_failure(self, mock_ssh_class, metric_service):
        """Test SSH connection with authentication failure."""
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        
        import paramiko
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        
        with pytest.raises(SSHConnectionError, match="Authentication failed"):
            metric_service._create_ssh_client(
                "192.168.1.100",
                22,
                "root",
                "password",
                "wrong_password"
            )


class TestMetricCollection:
    """Test full metric collection workflow."""
    
    def test_collect_metrics_success(
        self,
        metric_service,
        mock_vm,
        mock_credential,
        mock_db
    ):
        """Test successful metric collection."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credential
        
        # Mock credential decryption
        with patch.object(
            metric_service.credential_manager,
            'decrypt_ssh_key',
            return_value="decrypted_key"
        ):
            # Mock SSH operations
            mock_client = Mock()
            with patch.object(
                metric_service,
                '_create_ssh_client',
                return_value=mock_client
            ):
                with patch.object(
                    metric_service,
                    'detect_os',
                    return_value=MetricCollectorService.OS_LINUX
                ):
                    with patch.object(
                        metric_service,
                        'get_cpu_usage',
                        return_value=25.5
                    ):
                        with patch.object(
                            metric_service,
                            'get_memory_usage',
                            return_value=(2048, 4096)
                        ):
                            with patch.object(
                                metric_service,
                                'get_disk_usage',
                                return_value=(50.0, 100.0, 50.0)
                            ):
                                metrics = metric_service.collect_metrics(mock_vm)
                                
                                assert metrics.collection_success is True
                                assert metrics.cpu_usage_percent == 25.5
                                assert metrics.ram_used_mb == 2048
                                assert metrics.ram_total_mb == 4096
                                assert metrics.disk_used_gb == 50.0
                                assert metrics.disk_total_gb == 100.0
                                assert metrics.disk_usage_percent == 50.0
                                assert metrics.error_message is None
                                
                                # Verify SSH client was closed
                                mock_client.close.assert_called_once()
    
    def test_collect_metrics_no_credentials(
        self,
        metric_service,
        mock_vm,
        mock_db
    ):
        """Test metric collection when credentials are missing."""
        # Mock database query returning None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        metrics = metric_service.collect_metrics(mock_vm)
        
        assert metrics.collection_success is False
        assert "No credentials found" in metrics.error_message
    
    def test_collect_metrics_with_retry(
        self,
        metric_service,
        mock_vm,
        mock_credential,
        mock_db
    ):
        """Test metric collection with retry logic."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credential
        
        # Mock credential decryption
        with patch.object(
            metric_service.credential_manager,
            'decrypt_ssh_key',
            return_value="decrypted_key"
        ):
            # Mock SSH connection to fail twice, then succeed
            mock_client = Mock()
            with patch.object(
                metric_service,
                '_create_ssh_client',
                side_effect=[
                    SSHConnectionError("Connection timeout"),
                    SSHConnectionError("Connection refused"),
                    mock_client
                ]
            ):
                with patch.object(
                    metric_service,
                    'detect_os',
                    return_value=MetricCollectorService.OS_LINUX
                ):
                    with patch.object(
                        metric_service,
                        'get_cpu_usage',
                        return_value=25.5
                    ):
                        with patch.object(
                            metric_service,
                            'get_memory_usage',
                            return_value=(2048, 4096)
                        ):
                            with patch.object(
                                metric_service,
                                'get_disk_usage',
                                return_value=(50.0, 100.0, 50.0)
                            ):
                                # Mock time.sleep to speed up test
                                with patch('time.sleep'):
                                    metrics = metric_service.collect_metrics(mock_vm)
                                    
                                    assert metrics.collection_success is True
                                    assert metrics.cpu_usage_percent == 25.5
    
    def test_collect_metrics_all_retries_fail(
        self,
        metric_service,
        mock_vm,
        mock_credential,
        mock_db
    ):
        """Test metric collection when all retries fail."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credential
        
        # Mock credential decryption
        with patch.object(
            metric_service.credential_manager,
            'decrypt_ssh_key',
            return_value="decrypted_key"
        ):
            # Mock SSH connection to always fail
            with patch.object(
                metric_service,
                '_create_ssh_client',
                side_effect=SSHConnectionError("Connection failed")
            ):
                # Mock time.sleep to speed up test
                with patch('time.sleep'):
                    metrics = metric_service.collect_metrics(mock_vm)
                    
                    assert metrics.collection_success is False
                    assert "Failed to collect metrics after" in metrics.error_message


class TestStoreMetrics:
    """Test metric storage."""
    
    def test_store_metrics_success(self, metric_service, mock_db):
        """Test successful metric storage."""
        metrics = MetricData(
            cpu_usage_percent=25.5,
            ram_used_mb=2048,
            ram_total_mb=4096,
            disk_used_gb=50.0,
            disk_total_gb=100.0,
            disk_usage_percent=50.0,
            collection_success=True,
            error_message=None
        )
        
        metric_service.store_metrics(1, metrics)
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify metric object was created correctly
        added_metric = mock_db.add.call_args[0][0]
        assert added_metric.vm_id == 1
        assert added_metric.cpu_usage_percent == 25.5
        assert added_metric.collection_success is True
    
    def test_store_metrics_failure(self, metric_service, mock_db):
        """Test metric storage with database error."""
        metrics = MetricData(
            collection_success=False,
            error_message="Connection failed"
        )
        
        mock_db.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            metric_service.store_metrics(1, metrics)
        
        # Verify rollback was called
        mock_db.rollback.assert_called_once()


class TestGetMetricHistory:
    """Test metric history retrieval."""
    
    def test_get_metric_history(self, metric_service, mock_db):
        """Test retrieving metric history."""
        # Mock database query
        mock_metrics = [Mock(spec=Metric) for _ in range(10)]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_metrics
        
        results = metric_service.get_metric_history(1, limit=10)
        
        assert len(results) == 10
        assert results == mock_metrics
    
    def test_get_metric_history_default_limit(self, metric_service, mock_db):
        """Test retrieving metric history with default limit."""
        mock_metrics = [Mock(spec=Metric) for _ in range(100)]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_metrics
        
        results = metric_service.get_metric_history(1)
        
        # Verify limit was called with default value (1000)
        mock_query.filter.return_value.order_by.return_value.limit.assert_called_with(1000)
