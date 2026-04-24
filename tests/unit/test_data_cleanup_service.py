"""
Unit tests for DataCleanupService.

Tests data retention policies for ping results, metrics, and alerts.

Requirements: 4.6, 5.7
"""

import pytest
from datetime import datetime, timedelta

from vmledger.models.user import User
from vmledger.models.vm import VM
from vmledger.models.ping_result import PingResult
from vmledger.models.metric import Metric
from vmledger.models.alert import Alert
from vmledger.services.data_cleanup_service import DataCleanupService, DataCleanupServiceError


@pytest.fixture
def cleanup_service(db_session):
    """Create a DataCleanupService instance."""
    return DataCleanupService(db_session)


@pytest.fixture
def cleanup_test_user(db_session):
    """Create a test user for cleanup tests."""
    user = User(
        username="cleanupuser",
        email="cleanup@example.com",
        password_hash="hashed_password",
        encryption_salt="test_salt_cleanup"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def cleanup_test_vm(db_session, cleanup_test_user):
    """Create a test VM for cleanup tests."""
    vm = VM(
        user_id=cleanup_test_user.id,
        ip_address="192.168.1.100",
        hostname="test-vm",
        ssh_port=22,
        tags=[]  # Empty list for SQLite compatibility
    )
    db_session.add(vm)
    db_session.commit()
    db_session.refresh(vm)
    return vm


class TestPingResultsCleanup:
    """Test ping results cleanup with 100-record retention."""
    
    def test_cleanup_ping_results_with_no_records(self, cleanup_service, db_session):
        """Test cleanup when no ping results exist."""
        deleted = cleanup_service.cleanup_ping_results()
        assert deleted == 0
    
    def test_cleanup_ping_results_under_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records are under retention limit (100)."""
        # Create 50 ping results (under limit)
        for i in range(50):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        db_session.commit()
        
        # Cleanup should delete nothing
        deleted = cleanup_service.cleanup_ping_results()
        assert deleted == 0
        
        # Verify all records still exist
        remaining = db_session.query(PingResult).filter(PingResult.vm_id == cleanup_test_vm.id).count()
        assert remaining == 50
    
    def test_cleanup_ping_results_at_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records are exactly at retention limit (100)."""
        # Create exactly 100 ping results
        for i in range(100):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        db_session.commit()
        
        # Cleanup should delete nothing
        deleted = cleanup_service.cleanup_ping_results()
        assert deleted == 0
        
        # Verify all records still exist
        remaining = db_session.query(PingResult).filter(PingResult.vm_id == cleanup_test_vm.id).count()
        assert remaining == 100
    
    def test_cleanup_ping_results_over_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records exceed retention limit (100)."""
        # Create 150 ping results (50 over limit)
        for i in range(150):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        db_session.commit()
        
        # Cleanup should delete 50 oldest records
        deleted = cleanup_service.cleanup_ping_results()
        assert deleted == 50
        
        # Verify only 100 records remain
        remaining = db_session.query(PingResult).filter(PingResult.vm_id == cleanup_test_vm.id).count()
        assert remaining == 100
    
    def test_cleanup_ping_results_keeps_newest(self, cleanup_service, db_session, cleanup_test_vm):
        """Test that cleanup keeps the newest records."""
        # Create 150 ping results with known timestamps
        base_time = datetime.utcnow()
        for i in range(150):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=base_time - timedelta(minutes=i),
                success=True,
                response_time_ms=float(i),  # Use response time to identify records
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        db_session.commit()
        
        # Cleanup
        cleanup_service.cleanup_ping_results()
        
        # Verify the 100 newest records remain (response_time 0-99)
        remaining_results = (
            db_session.query(PingResult)
            .filter(PingResult.vm_id == cleanup_test_vm.id)
            .order_by(PingResult.timestamp.desc())
            .all()
        )
        
        assert len(remaining_results) == 100
        # Newest record should have response_time 0
        assert remaining_results[0].response_time_ms == 0.0
        # Oldest remaining record should have response_time 99
        assert remaining_results[-1].response_time_ms == 99.0
    
    def test_cleanup_ping_results_multiple_vms(self, cleanup_service, db_session, cleanup_test_user):
        """Test cleanup respects per-VM retention limits."""
        # Create two VMs
        vm1 = VM(user_id=cleanup_test_user.id, ip_address="192.168.1.101", hostname="vm1", ssh_port=22, tags=[])
        vm2 = VM(user_id=cleanup_test_user.id, ip_address="192.168.1.102", hostname="vm2", ssh_port=22, tags=[])
        db_session.add_all([vm1, vm2])
        db_session.commit()
        
        # Create 150 ping results for VM1
        for i in range(150):
            ping_result = PingResult(
                vm_id=vm1.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        
        # Create 120 ping results for VM2
        for i in range(120):
            ping_result = PingResult(
                vm_id=vm2.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        
        db_session.commit()
        
        # Cleanup should delete 50 from VM1 and 20 from VM2
        deleted = cleanup_service.cleanup_ping_results()
        assert deleted == 70  # 50 + 20
        
        # Verify each VM has exactly 100 records
        vm1_count = db_session.query(PingResult).filter(PingResult.vm_id == vm1.id).count()
        vm2_count = db_session.query(PingResult).filter(PingResult.vm_id == vm2.id).count()
        assert vm1_count == 100
        assert vm2_count == 100


class TestMetricsCleanup:
    """Test metrics cleanup with 1000-record retention."""
    
    def test_cleanup_metrics_with_no_records(self, cleanup_service, db_session):
        """Test cleanup when no metrics exist."""
        deleted = cleanup_service.cleanup_metrics()
        assert deleted == 0
    
    def test_cleanup_metrics_under_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records are under retention limit (1000)."""
        # Create 500 metrics (under limit)
        for i in range(500):
            metric = Metric(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        db_session.commit()
        
        # Cleanup should delete nothing
        deleted = cleanup_service.cleanup_metrics()
        assert deleted == 0
        
        # Verify all records still exist
        remaining = db_session.query(Metric).filter(Metric.vm_id == cleanup_test_vm.id).count()
        assert remaining == 500
    
    def test_cleanup_metrics_at_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records are exactly at retention limit (1000)."""
        # Create exactly 1000 metrics
        for i in range(1000):
            metric = Metric(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        db_session.commit()
        
        # Cleanup should delete nothing
        deleted = cleanup_service.cleanup_metrics()
        assert deleted == 0
        
        # Verify all records still exist
        remaining = db_session.query(Metric).filter(Metric.vm_id == cleanup_test_vm.id).count()
        assert remaining == 1000
    
    def test_cleanup_metrics_over_limit(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when records exceed retention limit (1000)."""
        # Create 1200 metrics (200 over limit)
        for i in range(1200):
            metric = Metric(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        db_session.commit()
        
        # Cleanup should delete 200 oldest records
        deleted = cleanup_service.cleanup_metrics()
        assert deleted == 200
        
        # Verify only 1000 records remain
        remaining = db_session.query(Metric).filter(Metric.vm_id == cleanup_test_vm.id).count()
        assert remaining == 1000
    
    def test_cleanup_metrics_keeps_newest(self, cleanup_service, db_session, cleanup_test_vm):
        """Test that cleanup keeps the newest records."""
        # Create 1200 metrics with known CPU values
        base_time = datetime.utcnow()
        for i in range(1200):
            metric = Metric(
                vm_id=cleanup_test_vm.id,
                timestamp=base_time - timedelta(minutes=i),
                cpu_usage_percent=float(i),  # Use CPU to identify records
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        db_session.commit()
        
        # Cleanup
        cleanup_service.cleanup_metrics()
        
        # Verify the 1000 newest records remain (CPU 0-999)
        remaining_metrics = (
            db_session.query(Metric)
            .filter(Metric.vm_id == cleanup_test_vm.id)
            .order_by(Metric.timestamp.desc())
            .all()
        )
        
        assert len(remaining_metrics) == 1000
        # Newest record should have CPU 0
        assert remaining_metrics[0].cpu_usage_percent == 0.0
        # Oldest remaining record should have CPU 999
        assert remaining_metrics[-1].cpu_usage_percent == 999.0
    
    def test_cleanup_metrics_multiple_vms(self, cleanup_service, db_session, cleanup_test_user):
        """Test cleanup respects per-VM retention limits."""
        # Create two VMs
        vm1 = VM(user_id=cleanup_test_user.id, ip_address="192.168.1.101", hostname="vm1", ssh_port=22)
        vm2 = VM(user_id=cleanup_test_user.id, ip_address="192.168.1.102", hostname="vm2", ssh_port=22)
        db_session.add_all([vm1, vm2])
        db_session.commit()
        
        # Create 1200 metrics for VM1
        for i in range(1200):
            metric = Metric(
                vm_id=vm1.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        
        # Create 1100 metrics for VM2
        for i in range(1100):
            metric = Metric(
                vm_id=vm2.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        
        db_session.commit()
        
        # Cleanup should delete 200 from VM1 and 100 from VM2
        deleted = cleanup_service.cleanup_metrics()
        assert deleted == 300  # 200 + 100
        
        # Verify each VM has exactly 1000 records
        vm1_count = db_session.query(Metric).filter(Metric.vm_id == vm1.id).count()
        vm2_count = db_session.query(Metric).filter(Metric.vm_id == vm2.id).count()
        assert vm1_count == 1000
        assert vm2_count == 1000


class TestAlertsCleanup:
    """Test alerts cleanup with 90-day retention."""
    
    def test_cleanup_alerts_with_no_records(self, cleanup_service, db_session):
        """Test cleanup when no alerts exist."""
        deleted = cleanup_service.cleanup_alerts()
        assert deleted == 0
    
    def test_cleanup_alerts_all_recent(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when all alerts are within retention period."""
        # Create 50 alerts within last 30 days
        for i in range(50):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        db_session.commit()
        
        # Cleanup should delete nothing
        deleted = cleanup_service.cleanup_alerts()
        assert deleted == 0
        
        # Verify all records still exist
        remaining = db_session.query(Alert).filter(Alert.vm_id == cleanup_test_vm.id).count()
        assert remaining == 50
    
    def test_cleanup_alerts_at_boundary(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup at exactly 90 days boundary."""
        # Create alert exactly 90 days old
        alert_90_days = Alert(
            vm_id=cleanup_test_vm.id,
            alert_type="VM_UNREACHABLE",
            sent_at=datetime.utcnow() - timedelta(days=90),
            success=True
        )
        db_session.add(alert_90_days)
        
        # Create alert 89 days old (should be kept)
        alert_89_days = Alert(
            vm_id=cleanup_test_vm.id,
            alert_type="VM_UNREACHABLE",
            sent_at=datetime.utcnow() - timedelta(days=89),
            success=True
        )
        db_session.add(alert_89_days)
        
        db_session.commit()
        
        # Cleanup should delete the 90-day-old alert
        deleted = cleanup_service.cleanup_alerts()
        assert deleted == 1
        
        # Verify only 1 record remains
        remaining = db_session.query(Alert).filter(Alert.vm_id == cleanup_test_vm.id).count()
        assert remaining == 1
    
    def test_cleanup_alerts_mixed_ages(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup with mix of old and recent alerts."""
        # Create 30 recent alerts (within 90 days)
        for i in range(30):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        
        # Create 20 old alerts (over 90 days)
        for i in range(91, 111):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        
        db_session.commit()
        
        # Cleanup should delete 20 old alerts
        deleted = cleanup_service.cleanup_alerts()
        assert deleted == 20
        
        # Verify only 30 recent alerts remain
        remaining = db_session.query(Alert).filter(Alert.vm_id == cleanup_test_vm.id).count()
        assert remaining == 30
    
    def test_cleanup_alerts_all_old(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup when all alerts are old."""
        # Create 50 alerts all over 90 days old
        for i in range(91, 141):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        db_session.commit()
        
        # Cleanup should delete all 50 alerts
        deleted = cleanup_service.cleanup_alerts()
        assert deleted == 50
        
        # Verify no alerts remain
        remaining = db_session.query(Alert).filter(Alert.vm_id == cleanup_test_vm.id).count()
        assert remaining == 0


class TestCleanupAll:
    """Test the cleanup_all method that runs all cleanup operations."""
    
    def test_cleanup_all_with_no_data(self, cleanup_service, db_session):
        """Test cleanup_all when no data exists."""
        stats = cleanup_service.cleanup_all()
        
        assert stats.ping_results_deleted == 0
        assert stats.metrics_deleted == 0
        assert stats.alerts_deleted == 0
    
    def test_cleanup_all_with_mixed_data(self, cleanup_service, db_session, cleanup_test_vm):
        """Test cleanup_all with data requiring cleanup."""
        # Create 150 ping results (50 over limit)
        for i in range(150):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        
        # Create 1200 metrics (200 over limit)
        for i in range(1200):
            metric = Metric(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                cpu_usage_percent=50.0,
                ram_used_mb=1024,
                ram_total_mb=2048,
                disk_used_gb=10.0,
                disk_total_gb=50.0,
                disk_usage_percent=20.0,
                collection_success=True
            )
            db_session.add(metric)
        
        # Create 20 old alerts (over 90 days)
        for i in range(91, 111):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        
        # Create 10 recent alerts (within 90 days)
        for i in range(10):
            alert = Alert(
                vm_id=cleanup_test_vm.id,
                alert_type="VM_UNREACHABLE",
                sent_at=datetime.utcnow() - timedelta(days=i),
                success=True
            )
            db_session.add(alert)
        
        db_session.commit()
        
        # Run cleanup_all
        stats = cleanup_service.cleanup_all()
        
        # Verify correct counts
        assert stats.ping_results_deleted == 50
        assert stats.metrics_deleted == 200
        assert stats.alerts_deleted == 20
        
        # Verify remaining counts
        assert db_session.query(PingResult).filter(PingResult.vm_id == cleanup_test_vm.id).count() == 100
        assert db_session.query(Metric).filter(Metric.vm_id == cleanup_test_vm.id).count() == 1000
        assert db_session.query(Alert).filter(Alert.vm_id == cleanup_test_vm.id).count() == 10
    
    def test_cleanup_all_stats_to_dict(self, cleanup_service, db_session, cleanup_test_vm):
        """Test CleanupStats to_dict method."""
        # Create some data
        for i in range(150):
            ping_result = PingResult(
                vm_id=cleanup_test_vm.id,
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                success=True,
                response_time_ms=10.0,
                icmp_success=True,
                tcp_success=True
            )
            db_session.add(ping_result)
        db_session.commit()
        
        # Run cleanup
        stats = cleanup_service.cleanup_all()
        stats_dict = stats.to_dict()
        
        # Verify dictionary format
        assert isinstance(stats_dict, dict)
        assert 'ping_results_deleted' in stats_dict
        assert 'metrics_deleted' in stats_dict
        assert 'alerts_deleted' in stats_dict
        assert stats_dict['ping_results_deleted'] == 50
