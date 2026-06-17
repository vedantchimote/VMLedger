"""
Health Check Service for executing Custom_Ping checks.

This service combines ICMP ping and TCP port connectivity tests to determine
VM reachability. It stores ping results and maintains history for monitoring.

Requirements: 4.1-4.6
"""

import logging
import socket
import time
from datetime import datetime
from typing import Optional, List

from ping3 import ping
from sqlalchemy.orm import Session

from vmledger.models.vm import VM
from vmledger.models.ping_result import PingResult
from vmledger.exceptions import HealthCheckServiceError


logger = logging.getLogger(__name__)


class PingResultData:
    """Data class for ping check results."""
    
    def __init__(
        self,
        success: bool,
        response_time_ms: Optional[float] = None,
        error_type: Optional[str] = None,
        icmp_success: bool = False,
        tcp_success: bool = False
    ):
        self.success = success
        self.response_time_ms = response_time_ms
        self.error_type = error_type
        self.icmp_success = icmp_success
        self.tcp_success = tcp_success


class HealthCheckService:
    """
    Manages health check operations for VMs.
    
    Implements Custom_Ping combining ICMP ping and TCP port connectivity tests.
    Maintains history of ping results for monitoring and alerting.
    """
    
    # Error type constants
    ERROR_ICMP_TIMEOUT = "ICMP_TIMEOUT"
    ERROR_TCP_REFUSED = "TCP_REFUSED"
    ERROR_HOST_UNREACHABLE = "HOST_UNREACHABLE"
    ERROR_TIMEOUT = "TIMEOUT"
    
    def __init__(self, db: Session):
        """
        Initialize the health check service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def check_icmp_ping(self, ip: str, timeout: int = 5) -> Optional[float]:
        """
        Execute ICMP ping to check host reachability.
        
        Uses ping3 library for cross-platform ICMP ping support.
        
        Args:
            ip: IP address to ping
            timeout: Timeout in seconds (default 5)
            
        Returns:
            Response time in milliseconds if successful, None if failed
            
        Requirements: 4.2 - Execute ICMP ping to VM's IP address
        """
        try:
            # ping3 returns response time in seconds, or None/False if failed
            response_time = ping(ip, timeout=timeout, unit='ms')
            
            if response_time is None or response_time is False:
                logger.debug(f"ICMP ping failed for {ip}")
                return None
            
            # ping3 with unit='ms' returns milliseconds
            logger.debug(f"ICMP ping successful for {ip}: {response_time}ms")
            return float(response_time)
            
        except Exception as e:
            logger.error(f"ICMP ping error for {ip}: {e}")
            return None
    
    def check_tcp_port(self, ip: str, port: int, timeout: int = 5) -> bool:
        """
        Check TCP port connectivity using socket connection.
        
        Args:
            ip: IP address to connect to
            port: TCP port number
            timeout: Timeout in seconds (default 5)
            
        Returns:
            True if TCP connection successful, False otherwise
            
        Requirements: 4.3 - Attempt TCP connection to VM's SSH port
        """
        sock = None
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Attempt connection
            start_time = time.time()
            result = sock.connect_ex((ip, port))
            elapsed = (time.time() - start_time) * 1000  # Convert to ms
            
            if result == 0:
                logger.debug(f"TCP connection successful to {ip}:{port} ({elapsed:.2f}ms)")
                return True
            else:
                logger.debug(f"TCP connection failed to {ip}:{port} (error code: {result})")
                return False
                
        except socket.timeout:
            logger.debug(f"TCP connection timeout to {ip}:{port}")
            return False
        except socket.gaierror as e:
            logger.error(f"TCP connection DNS error for {ip}:{port}: {e}")
            return False
        except Exception as e:
            logger.error(f"TCP connection error for {ip}:{port}: {e}")
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    
    def execute_ping(self, vm: VM) -> PingResultData:
        """
        Execute Custom_Ping combining ICMP and TCP checks.
        
        Success criteria: Both ICMP ping and TCP connection must succeed.
        Response time is measured from ICMP ping.
        
        Args:
            vm: VM object to ping
            
        Returns:
            PingResultData with check results
            
        Requirements: 4.1 - Execute Custom_Ping checks
        Requirements: 4.2 - Execute ICMP ping
        Requirements: 4.3 - Attempt TCP connection
        Requirements: 4.4 - Record timestamp and response time on success
        Requirements: 4.5 - Record failure timestamp and error type on failure
        """
        logger.info(f"Executing Custom_Ping for VM {vm.id} ({vm.hostname} - {vm.ip_address}:{vm.ssh_port})")
        
        # Execute ICMP ping
        icmp_response_time = self.check_icmp_ping(vm.ip_address, timeout=5)
        icmp_success = icmp_response_time is not None
        
        # Execute TCP port check
        tcp_success = self.check_tcp_port(vm.ip_address, vm.ssh_port, timeout=5)
        
        # Determine overall success and error type
        if icmp_success and tcp_success:
            # Both checks passed - success
            logger.info(
                f"Custom_Ping successful for VM {vm.id}: "
                f"ICMP={icmp_response_time:.2f}ms, TCP=OK"
            )
            return PingResultData(
                success=True,
                response_time_ms=icmp_response_time,
                error_type=None,
                icmp_success=True,
                tcp_success=True
            )
        
        # Determine specific error type
        error_type = None
        if not icmp_success and not tcp_success:
            # Both failed - complete timeout or host unreachable
            error_type = self.ERROR_TIMEOUT
        elif icmp_success and not tcp_success:
            # ICMP succeeded but TCP failed - port refused/filtered
            error_type = self.ERROR_TCP_REFUSED
        elif not icmp_success and tcp_success:
            # TCP succeeded but ICMP failed - ICMP timeout (unusual but possible)
            error_type = self.ERROR_ICMP_TIMEOUT
        
        logger.warning(
            f"Custom_Ping failed for VM {vm.id}: "
            f"ICMP={'OK' if icmp_success else 'FAIL'}, "
            f"TCP={'OK' if tcp_success else 'FAIL'}, "
            f"error_type={error_type}"
        )
        
        return PingResultData(
            success=False,
            response_time_ms=icmp_response_time if icmp_success else None,
            error_type=error_type,
            icmp_success=icmp_success,
            tcp_success=tcp_success
        )
    
    def store_ping_result(self, vm_id: int, result: PingResultData) -> None:
        """
        Store ping result to database and update VM status.
        
        Args:
            vm_id: VM ID
            result: PingResultData with check results
            
        Requirements: 4.4 - Record timestamp and response time on success
        Requirements: 4.5 - Record failure timestamp and error type on failure
        """
        try:
            # Create ping result record
            ping_result = PingResult(
                vm_id=vm_id,
                timestamp=datetime.utcnow(),
                success=result.success,
                response_time_ms=result.response_time_ms,
                error_type=result.error_type,
                icmp_success=result.icmp_success,
                tcp_success=result.tcp_success
            )
            
            self.db.add(ping_result)
            
            # Update VM status
            vm = self.db.query(VM).filter(VM.id == vm_id).first()
            if vm:
                if result.success:
                    vm.is_reachable = True
                    vm.last_seen = datetime.utcnow()
                else:
                    # Check the last 2 ping results (prior to the one we just added)
                    # To see if we have reached 3 consecutive failures
                    recent_pings = (
                        self.db.query(PingResult)
                        .filter(PingResult.vm_id == vm_id)
                        .order_by(PingResult.timestamp.desc())
                        .offset(1)  # Skip the one we just added
                        .limit(2)   # Look at the 2 before that
                        .all()
                    )
                    
                    # If we have at least 2 previous pings AND they both failed, mark offline
                    if len(recent_pings) == 2 and all(not p.success for p in recent_pings):
                        vm.is_reachable = False
                    # If there are no previous pings (brand new VM), mark it offline immediately
                    elif len(recent_pings) == 0:
                        vm.is_reachable = False
            
            self.db.commit()
            
            logger.debug(f"Stored ping result for VM {vm_id}: success={result.success}")
            
        except Exception as e:
            logger.error(f"Failed to store ping result for VM {vm_id}: {e}")
            self.db.rollback()
            raise HealthCheckServiceError(f"Failed to store ping result: {e}")
    
    def get_ping_history(self, vm_id: int, limit: int = 100) -> List[PingResult]:
        """
        Retrieve ping history for a VM.
        
        Args:
            vm_id: VM ID
            limit: Maximum number of results to return (default 100)
            
        Returns:
            List of PingResult objects ordered by timestamp descending
            
        Requirements: 4.6 - Maintain history of last 100 Custom_Ping results per VM
        """
        try:
            results = (
                self.db.query(PingResult)
                .filter(PingResult.vm_id == vm_id)
                .order_by(PingResult.timestamp.desc())
                .limit(limit)
                .all()
            )
            
            logger.debug(f"Retrieved {len(results)} ping results for VM {vm_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve ping history for VM {vm_id}: {e}")
            raise HealthCheckServiceError(f"Failed to retrieve ping history: {e}")
