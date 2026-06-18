"""
Shared SSH utilities for connection management and command execution.
"""

import logging
from typing import Tuple
from io import StringIO

import paramiko

from vmledger.config import settings
from vmledger.exceptions import SSHConnectionError, MetricCollectorServiceError


logger = logging.getLogger(__name__)


class CommandExecutionError(MetricCollectorServiceError):
    """Raised when SSH command execution fails."""
    pass


class SSHUtils:
    """
    Shared utilities for SSH connections and command execution.
    """

    @staticmethod
    def create_ssh_client(
        ip_address: str,
        port: int,
        username: str,
        auth_type: str,
        credential: str,
        connection_timeout: int = settings.ssh_connection_timeout
    ) -> paramiko.SSHClient:
        """
        Create and connect SSH client with authentication.
        
        Args:
            ip_address: Target IP address
            port: SSH port
            username: SSH username
            auth_type: 'ssh_key' or 'password'
            credential: Decrypted SSH key or password
            connection_timeout: Timeout for connection in seconds
            
        Returns:
            Connected SSHClient instance
            
        Raises:
            SSHConnectionError: If connection fails
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if auth_type == 'ssh_key':
                # Load private key from string
                key_file = StringIO(credential)
                
                # Try different key types
                private_key = None
                key_classes = [
                    paramiko.RSAKey,
                    paramiko.ECDSAKey,
                    paramiko.Ed25519Key
                ]
                
                # Add DSSKey if available (deprecated in newer Paramiko versions)
                if hasattr(paramiko, 'DSSKey'):
                    key_classes.insert(1, paramiko.DSSKey)
                
                for key_class in key_classes:
                    try:
                        key_file.seek(0)
                        private_key = key_class.from_private_key(key_file)
                        break
                    except paramiko.SSHException:
                        continue
                
                if private_key is None:
                    raise SSHConnectionError("Failed to load SSH private key")
                
                # Connect with private key
                client.connect(
                    hostname=ip_address,
                    port=port,
                    username=username,
                    pkey=private_key,
                    timeout=connection_timeout,
                    banner_timeout=connection_timeout,
                    auth_timeout=connection_timeout
                )
            else:
                # Connect with password
                client.connect(
                    hostname=ip_address,
                    port=port,
                    username=username,
                    password=credential,
                    timeout=connection_timeout,
                    banner_timeout=connection_timeout,
                    auth_timeout=connection_timeout
                )
            
            logger.debug(f"SSH connection established to {ip_address}:{port}")
            return client
            
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed for {ip_address}:{port}: {e}")
            raise SSHConnectionError(f"Authentication failed: {e}")
        except paramiko.SSHException as e:
            logger.error(f"SSH connection error for {ip_address}:{port}: {e}")
            raise SSHConnectionError(f"SSH error: {e}")
        except Exception as e:
            logger.error(f"Failed to connect to {ip_address}:{port}: {e}")
            raise SSHConnectionError(f"Connection failed: {e}")

    @staticmethod
    def execute_command(
        client: paramiko.SSHClient,
        command: str,
        command_timeout: int = settings.ssh_command_timeout
    ) -> Tuple[str, str, int]:
        """
        Execute command via SSH with timeout.
        
        Args:
            client: Connected SSHClient
            command: Command to execute
            command_timeout: Timeout for execution in seconds
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            
        Raises:
            CommandExecutionError: If command execution fails
        """
        try:
            # Execute command with timeout
            stdin, stdout, stderr = client.exec_command(
                command,
                timeout=command_timeout
            )
            
            # Read output with timeout
            stdout_data = stdout.read().decode('utf-8').strip()
            stderr_data = stderr.read().decode('utf-8').strip()
            exit_code = stdout.channel.recv_exit_status()
            
            logger.debug(
                f"Command executed: {command[:50]}... "
                f"(exit_code={exit_code}, stdout_len={len(stdout_data)})"
            )
            
            return stdout_data, stderr_data, exit_code
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandExecutionError(f"Failed to execute command: {e}")
