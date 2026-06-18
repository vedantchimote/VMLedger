"""
Metric Collector Service for SSH-based resource metric collection.

This service implements agentless metric collection via SSH, supporting both
Linux and macOS operating systems with OS-specific commands. It collects CPU,
RAM, and disk usage metrics without requiring agent installation on target VMs.

Requirements: 5.1-5.7
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Tuple
from io import StringIO

import paramiko
from sqlalchemy.orm import Session

from vmledger.models.vm import VM
from vmledger.models.credential import Credential
from vmledger.models.metric import Metric
from vmledger.models.service_check import ServiceConfig, ServiceStatus
from vmledger.services.credential_manager import CredentialManager
from vmledger.config import settings
from vmledger.exceptions import (
    MetricCollectorServiceError,
    SSHConnectionError,
    MetricCollectionError
)


logger = logging.getLogger(__name__)


class CommandExecutionError(MetricCollectorServiceError):
    """Raised when SSH command execution fails."""
    pass


class MetricData:
    """Data class for collected metrics."""
    
    def __init__(
        self,
        cpu_usage_percent: Optional[float] = None,
        ram_used_mb: Optional[int] = None,
        ram_total_mb: Optional[int] = None,
        disk_used_gb: Optional[float] = None,
        disk_total_gb: Optional[float] = None,
        disk_usage_percent: Optional[float] = None,
        collection_success: bool = False,
        error_message: Optional[str] = None
    ):
        self.cpu_usage_percent = cpu_usage_percent
        self.ram_used_mb = ram_used_mb
        self.ram_total_mb = ram_total_mb
        self.disk_used_gb = disk_used_gb
        self.disk_total_gb = disk_total_gb
        self.disk_usage_percent = disk_usage_percent
        self.collection_success = collection_success
        self.error_message = error_message


class MetricCollectorService:
    """
    Manages SSH-based metric collection from VMs.
    
    Supports both Linux and macOS with OS-specific commands.
    Implements connection management, retry logic, and timeout handling.
    """
    
    # OS type constants
    OS_LINUX = "Linux"
    OS_MACOS = "Darwin"
    OS_UNKNOWN = "Unknown"
    
    def __init__(self, db: Session):
        """
        Initialize the metric collector service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.credential_manager = CredentialManager(db)
        self.connection_timeout = settings.ssh_connection_timeout
        self.command_timeout = settings.ssh_command_timeout
        self.max_retries = settings.ssh_max_retries
        self.retry_delay = settings.ssh_retry_delay
    
    def _create_ssh_client(
        self,
        ip_address: str,
        port: int,
        username: str,
        auth_type: str,
        credential: str
    ) -> paramiko.SSHClient:
        """
        Create and connect SSH client with authentication.
        
        Args:
            ip_address: Target IP address
            port: SSH port
            username: SSH username
            auth_type: 'ssh_key' or 'password'
            credential: Decrypted SSH key or password
            
        Returns:
            Connected SSHClient instance
            
        Raises:
            SSHConnectionError: If connection fails
        """
        from vmledger.services.ssh_utils import SSHUtils
        return SSHUtils.create_ssh_client(
            ip_address=ip_address,
            port=port,
            username=username,
            auth_type=auth_type,
            credential=credential,
            connection_timeout=self.connection_timeout
        )
    
    def _execute_command(
        self,
        client: paramiko.SSHClient,
        command: str
    ) -> Tuple[str, str, int]:
        """
        Execute command via SSH with timeout.
        
        Args:
            client: Connected SSHClient
            command: Command to execute
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            
        Raises:
            CommandExecutionError: If command execution fails
        """
        from vmledger.services.ssh_utils import SSHUtils
        return SSHUtils.execute_command(
            client=client,
            command=command,
            command_timeout=self.command_timeout
        )
    
    def _check_services(self, client: paramiko.SSHClient, vm: VM) -> None:
        """
        Check health of all configured services for this VM.
        """
        services = self.db.query(ServiceConfig).filter(
            ServiceConfig.vm_id == vm.id,
            ServiceConfig.enabled == True
        ).all()
        
        if not services:
            return
            
        for svc in services:
            command = svc.check_command or f"systemctl is-active {svc.service_name}"
            try:
                from vmledger.services.ssh_utils import SSHUtils
                stdout, stderr, exit_code = SSHUtils.execute_command(
                    client=client, 
                    command=command,
                    command_timeout=10
                )
                status = stdout.strip() if stdout else "unknown"
                # If command fails completely (e.g. not found), it might return empty or error
                if exit_code != 0 and not status:
                    status = "failed"
            except Exception as e:
                logger.error(f"Service check failed for {svc.service_name}: {e}")
                status = "error"
                
            # Upsert status
            existing_status = self.db.query(ServiceStatus).filter(
                ServiceStatus.vm_id == vm.id,
                ServiceStatus.service_name == svc.service_name
            ).first()
            
            if existing_status:
                existing_status.status = status
            else:
                new_status = ServiceStatus(
                    vm_id=vm.id,
                    service_name=svc.service_name,
                    status=status
                )
                self.db.add(new_status)
                
        self.db.commit()

    def detect_os(self, client: paramiko.SSHClient) -> str:
        """
        Detect operating system using uname command.
        
        Args:
            client: Connected SSHClient
            
        Returns:
            OS type: 'Linux', 'Darwin' (macOS), or 'Unknown'
            
        Requirements: Design - Implement OS detection using uname command
        """
        try:
            stdout, stderr, exit_code = self._execute_command(client, "uname -s")
            
            if exit_code == 0 and stdout:
                os_type = stdout.strip()
                logger.info(f"Detected OS: {os_type}")
                
                if os_type == "Linux":
                    return self.OS_LINUX
                elif os_type == "Darwin":
                    return self.OS_MACOS
                else:
                    logger.warning(f"Unknown OS type: {os_type}")
                    return self.OS_UNKNOWN
            else:
                logger.warning(f"OS detection failed: {stderr}")
                return self.OS_UNKNOWN
                
        except Exception as e:
            logger.error(f"OS detection error: {e}")
            return self.OS_UNKNOWN
    
    def get_cpu_usage(
        self,
        client: paramiko.SSHClient,
        os_type: str
    ) -> Optional[float]:
        """
        Get CPU usage percentage via SSH.
        
        Uses OS-specific commands:
        - Linux: top -bn1 | grep "Cpu(s)" | awk '{print $2}'
        - macOS: top -l 1 | grep "CPU usage" | awk '{print $3}'
        
        Args:
            client: Connected SSHClient
            os_type: Operating system type
            
        Returns:
            CPU usage percentage, or None if failed
            
        Requirements: 5.1 - Retrieve CPU usage percentage via SSH
        """
        try:
            if os_type == self.OS_LINUX:
                command = "top -bn1 | grep \"Cpu(s)\" | awk '{print $2}'"
            elif os_type == self.OS_MACOS:
                command = "top -l 1 | grep \"CPU usage\" | awk '{print $3}'"
            else:
                # Default to Linux command
                command = "top -bn1 | grep \"Cpu(s)\" | awk '{print $2}'"
            
            stdout, stderr, exit_code = self._execute_command(client, command)
            
            if exit_code == 0 and stdout:
                # Parse CPU percentage (remove % sign if present)
                cpu_str = stdout.strip().replace('%', '').replace(',', '.')
                cpu_usage = float(cpu_str)
                logger.debug(f"CPU usage: {cpu_usage}%")
                return cpu_usage
            else:
                logger.warning(f"Failed to get CPU usage: {stderr}")
                return None
                
        except ValueError as e:
            logger.error(f"Failed to parse CPU usage: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return None
    
    def get_memory_usage(
        self,
        client: paramiko.SSHClient,
        os_type: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Get memory usage (used and total) via SSH.
        
        Uses OS-specific commands:
        - Linux: free -m | grep Mem | awk '{print $3,$2}'
        - macOS: vm_stat | grep "Pages active" + calculations
        
        Args:
            client: Connected SSHClient
            os_type: Operating system type
            
        Returns:
            Tuple of (ram_used_mb, ram_total_mb), or (None, None) if failed
            
        Requirements: 5.2 - Retrieve RAM usage (used and total) via SSH
        """
        try:
            if os_type == self.OS_LINUX:
                command = "free -m | grep Mem | awk '{print $3,$2}'"
                stdout, stderr, exit_code = self._execute_command(client, command)
                
                if exit_code == 0 and stdout:
                    parts = stdout.strip().split()
                    if len(parts) >= 2:
                        ram_used_mb = int(parts[0])
                        ram_total_mb = int(parts[1])
                        logger.debug(f"RAM: {ram_used_mb}/{ram_total_mb} MB")
                        return ram_used_mb, ram_total_mb
                        
            elif os_type == self.OS_MACOS:
                # macOS requires more complex calculation
                # Get page size
                stdout, _, exit_code = self._execute_command(
                    client,
                    "pagesize"
                )
                if exit_code != 0:
                    return None, None
                
                page_size = int(stdout.strip())
                
                # Get memory statistics
                stdout, _, exit_code = self._execute_command(
                    client,
                    "vm_stat | grep -E 'Pages (active|wired|occupied by compressor|free|inactive)' | awk '{print $3}' | sed 's/\\.//'"
                )
                if exit_code != 0:
                    return None, None
                
                # Parse vm_stat output
                lines = stdout.strip().split('\n')
                if len(lines) >= 3:
                    # Simplified calculation: active + wired as used
                    # This is approximate for macOS
                    active_pages = int(lines[0])
                    wired_pages = int(lines[1])
                    
                    # Get total memory
                    stdout, _, exit_code = self._execute_command(
                        client,
                        "sysctl hw.memsize | awk '{print $2}'"
                    )
                    if exit_code != 0:
                        return None, None
                    
                    total_bytes = int(stdout.strip())
                    total_mb = total_bytes // (1024 * 1024)
                    used_mb = ((active_pages + wired_pages) * page_size) // (1024 * 1024)
                    
                    logger.debug(f"RAM (macOS): {used_mb}/{total_mb} MB")
                    return used_mb, total_mb
            
            logger.warning("Failed to get memory usage")
            return None, None
            
        except ValueError as e:
            logger.error(f"Failed to parse memory usage: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return None, None
    
    def get_disk_usage(
        self,
        client: paramiko.SSHClient
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Get disk usage via SSH.
        
        Uses df command (same for Linux and macOS):
        df -h / | tail -1 | awk '{print $3,$2,$5}'
        
        Args:
            client: Connected SSHClient
            
        Returns:
            Tuple of (disk_used_gb, disk_total_gb, disk_usage_percent),
            or (None, None, None) if failed
            
        Requirements: 5.3 - Retrieve disk usage (used, total, percentage) via SSH
        """
        try:
            command = "df -h / | tail -1 | awk '{print $3,$2,$5}'"
            stdout, stderr, exit_code = self._execute_command(client, command)
            
            if exit_code == 0 and stdout:
                parts = stdout.strip().split()
                if len(parts) >= 3:
                    # Parse disk sizes (can be in G, M, T, etc.)
                    disk_used_str = parts[0]
                    disk_total_str = parts[1]
                    disk_percent_str = parts[2].replace('%', '')
                    
                    # Convert to GB
                    disk_used_gb = self._parse_disk_size(disk_used_str)
                    disk_total_gb = self._parse_disk_size(disk_total_str)
                    disk_usage_percent = float(disk_percent_str)
                    
                    logger.debug(
                        f"Disk: {disk_used_gb:.2f}/{disk_total_gb:.2f} GB "
                        f"({disk_usage_percent}%)"
                    )
                    return disk_used_gb, disk_total_gb, disk_usage_percent
            
            logger.warning(f"Failed to get disk usage: {stderr}")
            return None, None, None
            
        except ValueError as e:
            logger.error(f"Failed to parse disk usage: {e}")
            return None, None, None
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return None, None, None
    
    def _parse_disk_size(self, size_str: str) -> float:
        """
        Parse disk size string to GB.
        
        Handles formats like: 10G, 512M, 1.5T, 100K
        
        Args:
            size_str: Size string from df command
            
        Returns:
            Size in GB
        """
        size_str = size_str.strip().upper()
        
        # Extract number and unit
        if size_str[-1].isalpha():
            number = float(size_str[:-1])
            unit = size_str[-1]
        else:
            # No unit, assume bytes
            number = float(size_str)
            unit = 'B'
        
        # Convert to GB
        conversions = {
            'K': 1 / (1024 * 1024),      # KB to GB
            'M': 1 / 1024,                 # MB to GB
            'G': 1,                        # GB to GB
            'T': 1024,                     # TB to GB
            'P': 1024 * 1024,              # PB to GB
            'B': 1 / (1024 * 1024 * 1024) # Bytes to GB
        }
        
        return number * conversions.get(unit, 1)
    
    def collect_metrics(self, vm: VM) -> MetricData:
        """
        Collect all metrics from a VM via SSH.
        
        Orchestrates OS detection and metric collection with retry logic.
        
        Args:
            vm: VM object to collect metrics from
            
        Returns:
            MetricData with collected metrics
            
        Requirements: 5.1 - Retrieve CPU usage via SSH
        Requirements: 5.2 - Retrieve RAM usage via SSH
        Requirements: 5.3 - Retrieve disk usage via SSH
        Requirements: 5.4 - Use stored SSH credentials for authentication
        Requirements: 5.5 - Log error and mark VM unreachable on SSH failure
        """
        logger.info(
            f"Collecting metrics for VM {vm.id} "
            f"({vm.hostname} - {vm.ip_address}:{vm.ssh_port})"
        )
        
        # Retrieve credentials
        credential = self.db.query(Credential).filter(
            Credential.vm_id == vm.id
        ).first()
        
        if not credential:
            error_msg = f"No credentials found for VM {vm.id}"
            logger.error(error_msg)
            return MetricData(
                collection_success=False,
                error_message=error_msg
            )
        
        # Decrypt credentials
        try:
            if credential.auth_type == 'ssh_key':
                decrypted_credential = self.credential_manager.decrypt_ssh_key(
                    vm.user_id,
                    credential.encrypted_credential
                )
            else:
                decrypted_credential = self.credential_manager.decrypt_password(
                    vm.user_id,
                    credential.encrypted_credential
                )
        except Exception as e:
            error_msg = f"Failed to decrypt credentials for VM {vm.id}: {e}"
            logger.error(error_msg)
            return MetricData(
                collection_success=False,
                error_message=error_msg
            )
        
        # Retry logic
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    f"Metric collection attempt {attempt}/{self.max_retries} "
                    f"for VM {vm.id}"
                )
                
                # Create SSH connection
                client = self._create_ssh_client(
                    vm.ip_address,
                    vm.ssh_port,
                    credential.ssh_username,
                    credential.auth_type,
                    decrypted_credential
                )
                
                try:
                    # Detect OS
                    os_type = self.detect_os(client)
                    
                    # Collect metrics
                    cpu_usage = self.get_cpu_usage(client, os_type)
                    ram_used, ram_total = self.get_memory_usage(client, os_type)
                    disk_used, disk_total, disk_percent = self.get_disk_usage(client)
                    
                    # Check service health
                    try:
                        self._check_services(client, vm)
                    except Exception as e:
                        logger.error(f"Failed to check services for VM {vm.id}: {e}")
                    
                    # Check if we got at least some metrics
                    if cpu_usage is not None or ram_used is not None or disk_used is not None:
                        logger.info(
                            f"Successfully collected metrics for VM {vm.id} "
                            f"(attempt {attempt})"
                        )
                        return MetricData(
                            cpu_usage_percent=cpu_usage,
                            ram_used_mb=ram_used,
                            ram_total_mb=ram_total,
                            disk_used_gb=disk_used,
                            disk_total_gb=disk_total,
                            disk_usage_percent=disk_percent,
                            collection_success=True,
                            error_message=None
                        )
                    else:
                        last_error = "Failed to collect any metrics"
                        
                finally:
                    # Always close SSH connection
                    try:
                        client.close()
                    except Exception:
                        pass
                        
            except (SSHConnectionError, CommandExecutionError) as e:
                last_error = str(e)
                logger.warning(
                    f"Metric collection attempt {attempt}/{self.max_retries} "
                    f"failed for VM {vm.id}: {e}"
                )
                
                # Wait before retry (except on last attempt)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Unexpected error collecting metrics for VM {vm.id} "
                    f"(attempt {attempt}): {e}",
                    exc_info=True
                )
        
        logger.error(f"All metric collection attempts failed for VM {vm.id}")
        return MetricData(
            collection_success=False,
            error_message=last_error
        )

    def fetch_vm_specs(self, vm_id: int) -> dict:
        """
        Fetch detailed hardware and OS specifications from a VM via SSH.
        
        Args:
            vm_id: ID of the VM
            
        Returns:
            Dictionary containing OS, CPU, RAM, and Disk specifications
        """
        vm = self.db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            raise MetricCollectorServiceError(f"VM not found: {vm_id}")
            
        credential = self.db.query(Credential).filter(Credential.vm_id == vm_id).first()
        if not credential:
            raise MetricCollectorServiceError(f"No credentials found for VM {vm_id}")

        # Decrypt credentials using the same pattern as collect_metrics_for_vm
        try:
            if credential.auth_type == 'ssh_key':
                decrypted_credential = self.credential_manager.decrypt_ssh_key(
                    vm.user_id,
                    credential.encrypted_credential
                )
            else:
                decrypted_credential = self.credential_manager.decrypt_password(
                    vm.user_id,
                    credential.encrypted_credential
                )
        except Exception as e:
            raise MetricCollectorServiceError(f"Failed to decrypt credentials for VM {vm_id}: {e}")

        try:
            client = self._create_ssh_client(
                ip_address=vm.ip_address,
                port=vm.ssh_port,
                username=credential.ssh_username,
                auth_type=credential.auth_type,
                credential=decrypted_credential
            )
            
            try:
                os_type = self.detect_os(client)
                specs = {
                    "os_type": os_type,
                    "os_name": "Unknown",
                    "kernel": "Unknown",
                    "cpu_model": "Unknown",
                    "cpu_cores": 0,
                    "ram_total_gb": 0,
                    "partitions": []
                }
                
                # OS details
                stdout, _, exit_code = self._execute_command(client, "uname -r")
                if exit_code == 0:
                    specs["kernel"] = stdout.strip()
                    
                if os_type == self.OS_LINUX:
                    stdout, _, exit_code = self._execute_command(client, "cat /etc/os-release | grep PRETTY_NAME")
                    if exit_code == 0 and "PRETTY_NAME=" in stdout:
                        specs["os_name"] = stdout.split("=")[1].strip().strip('"')
                        
                    # CPU details
                    stdout, _, exit_code = self._execute_command(client, "lscpu | grep 'Model name'")
                    if exit_code == 0 and ":" in stdout:
                        specs["cpu_model"] = stdout.split(":")[1].strip()
                        
                    stdout, _, exit_code = self._execute_command(client, "nproc")
                    if exit_code == 0:
                        try:
                            specs["cpu_cores"] = int(stdout.strip())
                        except ValueError:
                            pass
                            
                    # RAM details
                    stdout, _, exit_code = self._execute_command(client, "free -m | grep Mem")
                    if exit_code == 0:
                        parts = stdout.split()
                        if len(parts) >= 2:
                            try:
                                specs["ram_total_gb"] = round(int(parts[1]) / 1024, 2)
                            except ValueError:
                                pass
                                
                    # Partitions
                    stdout, _, exit_code = self._execute_command(client, "df -h")
                    if exit_code == 0:
                        lines = stdout.strip().split('\n')
                        for line in lines[1:]:
                            parts = line.split()
                            if len(parts) >= 6 and not parts[0].startswith('tmpfs') and not parts[0].startswith('devtmpfs'):
                                specs["partitions"].append({
                                    "filesystem": parts[0],
                                    "size": parts[1],
                                    "used": parts[2],
                                    "avail": parts[3],
                                    "use_percent": parts[4],
                                    "mounted_on": parts[5]
                                })
                
                return specs
                
            finally:
                client.close()
                
        except Exception as e:
            logger.error(f"Failed to fetch specs for VM {vm.id}: {e}")
            raise MetricCollectorServiceError(f"Failed to fetch specs: {e}")
            
    def store_metrics(self, vm_id: int, metrics: MetricData) -> None:
        """
        Store collected metrics to database.
        
        Args:
            vm_id: VM ID
            metrics: MetricData with collected metrics
            
        Requirements: 5.7 - Store most recent 1000 metric data points per VM
        """
        try:
            # Create metric record
            metric = Metric(
                vm_id=vm_id,
                timestamp=datetime.utcnow(),
                cpu_usage_percent=metrics.cpu_usage_percent,
                ram_used_mb=metrics.ram_used_mb,
                ram_total_mb=metrics.ram_total_mb,
                disk_used_gb=metrics.disk_used_gb,
                disk_total_gb=metrics.disk_total_gb,
                disk_usage_percent=metrics.disk_usage_percent,
                collection_success=metrics.collection_success,
                error_message=metrics.error_message
            )
            
            self.db.add(metric)
            self.db.commit()
            
            logger.debug(
                f"Stored metrics for VM {vm_id}: "
                f"success={metrics.collection_success}"
            )
            
        except Exception as e:
            logger.error(f"Failed to store metrics for VM {vm_id}: {e}")
            self.db.rollback()
            raise MetricCollectorServiceError(f"Failed to store metrics: {e}")
    
    def get_metric_history(
        self,
        vm_id: int,
        limit: int = 1000
    ) -> List[Metric]:
        """
        Retrieve metric history for a VM.
        
        Args:
            vm_id: VM ID
            limit: Maximum number of results to return (default 1000)
            
        Returns:
            List of Metric objects ordered by timestamp descending
            
        Requirements: 5.7 - Store most recent 1000 metric data points per VM
        """
        try:
            results = (
                self.db.query(Metric)
                .filter(Metric.vm_id == vm_id)
                .order_by(Metric.timestamp.desc())
                .limit(limit)
                .all()
            )
            
            logger.debug(f"Retrieved {len(results)} metric records for VM {vm_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve metric history for VM {vm_id}: {e}")
            raise MetricCollectorServiceError(f"Failed to retrieve metric history: {e}")
