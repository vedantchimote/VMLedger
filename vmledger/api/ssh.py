"""
SSH Terminal API endpoints.

This module provides WebSocket endpoints for connecting to VMs via SSH
directly from the web interface.
"""

import logging
import json
import asyncio
import threading
from typing import Dict, Any, Optional
from io import StringIO

import paramiko
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session

from vmledger.database import get_db
from vmledger.models.vm import VM
from vmledger.models.credential import Credential
from vmledger.services.auth_service import AuthService
from vmledger.services.credential_manager import CredentialManager


logger = logging.getLogger(__name__)

router = APIRouter()


class SSHSessionManager:
    """Manages an interactive SSH session via WebSockets."""

    def __init__(self, websocket: WebSocket, client: paramiko.SSHClient, channel: paramiko.Channel):
        self.websocket = websocket
        self.client = client
        self.channel = channel
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = True
        self.reader_thread: Optional[threading.Thread] = None

    def start_reader_thread(self):
        """Starts a background thread to read from the blocking SSH channel."""
        def reader_loop():
            try:
                # Need to run queue.put_nowait using the main event loop
                # So we capture the current loop before starting the thread
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If there's no event loop in this thread, we can't easily push to an asyncio.Queue from it
                # We'll use a thread-safe way
                pass
                
            while self.running:
                if self.channel.recv_ready():
                    try:
                        data = self.channel.recv(4096)
                        if not data:
                            self.running = False
                            break
                        
                        # We use call_soon_threadsafe if we captured the loop, but it's easier to just use the
                        # asyncio.run_coroutine_threadsafe if we know the loop.
                        # Wait, we can pass the loop in.
                        pass
                    except Exception as e:
                        logger.error(f"SSH reader thread error: {e}")
                        self.running = False
                        break
                else:
                    if self.channel.exit_status_ready():
                        self.running = False
                        break
                    # Avoid CPU spinning
                    import time
                    time.sleep(0.01)

        # Better approach for queueing data from thread to async loop:
        self._loop = asyncio.get_running_loop()
        
        def safe_reader_loop():
            while self.running:
                try:
                    # Blocking read, returns empty bytes on EOF
                    data = self.channel.recv(4096)
                    if not data:
                        logger.debug("SSH channel closed by remote host.")
                        self.running = False
                        # Signal EOF to the async queue
                        self._loop.call_soon_threadsafe(self.queue.put_nowait, None)
                        break
                    
                    self._loop.call_soon_threadsafe(self.queue.put_nowait, data)
                except Exception as e:
                    logger.error(f"SSH reader thread error: {e}")
                    self.running = False
                    self._loop.call_soon_threadsafe(self.queue.put_nowait, None)
                    break

        self.reader_thread = threading.Thread(target=safe_reader_loop, daemon=True)
        self.reader_thread.start()

    async def consume_queue(self):
        """Reads from the queue and sends to WebSocket."""
        try:
            while self.running:
                data = await self.queue.get()
                if data is None:
                    # EOF
                    break
                # WebSocket expects string for text, we can send text or bytes.
                # xterm.js usually expects string.
                text_data = data.decode("utf-8", errors="replace")
                await self.websocket.send_text(text_data)
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            self.running = False

    async def consume_websocket(self):
        """Reads from WebSocket and writes to SSH channel."""
        try:
            while self.running:
                message = await self.websocket.receive_text()
                
                # Check if it's a JSON command (like resize)
                if message.startswith("{") and message.endswith("}"):
                    try:
                        data = json.loads(message)
                        if data.get("type") == "resize":
                            cols = data.get("cols", 80)
                            rows = data.get("rows", 24)
                            self.channel.resize_pty(width=cols, height=rows)
                            continue
                    except json.JSONDecodeError:
                        pass # Not JSON, treat as raw input
                
                # Send raw input to SSH channel
                # We use to_thread to avoid blocking the event loop
                await asyncio.to_thread(self.channel.sendall, message)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected by client.")
            self.running = False
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            self.running = False

    def close(self):
        """Cleans up resources."""
        self.running = False
        try:
            self.channel.close()
        except Exception:
            pass
        try:
            self.client.close()
        except Exception:
            pass


@router.websocket("/ws/vms/{vm_id}/ssh")
async def ssh_terminal_endpoint(
    websocket: WebSocket,
    vm_id: int,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for SSH terminal proxy.
    """
    await websocket.accept()
    
    # Needs its own DB session since Depends() doesn't always work perfectly for WebSockets
    # if connection lasts a long time. But we can use a temporary session to authenticate and fetch.
    db: Session = next(get_db())
    session_manager = None
    
    try:
        # 1. Authenticate user
        auth_service = AuthService(db)
        try:
            user = auth_service.validate_token(token)
        except Exception as e:
            logger.warning(f"SSH WebSocket auth failed: {e}")
            await websocket.send_text(f"\\r\\n[Error: Authentication failed: {e}]\\r\\n")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 2. Fetch VM and verify ownership
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            await websocket.send_text(f"\\r\\n[Error: VM {vm_id} not found]\\r\\n")
            await websocket.close(code=status.WS_1004_NO_STATUS_RCVD)
            return
            
        if vm.user_id != user.id:
            await websocket.send_text(f"\\r\\n[Error: Access denied to VM {vm_id}]\\r\\n")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 3. Fetch credentials
        credential = db.query(Credential).filter(Credential.vm_id == vm_id).first()
        if not credential:
            await websocket.send_text(f"\\r\\n[Error: No SSH credentials found for VM {vm_id}]\\r\\n")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # 4. Decrypt credentials
        cred_manager = CredentialManager(db)
        try:
            if credential.auth_type == 'ssh_key':
                decrypted_credential = cred_manager.decrypt_ssh_key(user.id, credential.encrypted_credential)
            else:
                decrypted_credential = cred_manager.decrypt_password(user.id, credential.encrypted_credential)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for VM {vm_id}: {e}")
            await websocket.send_text("\\r\\n[Error: Failed to decrypt credentials]\\r\\n")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # We have what we need, close DB session
        db.close()
        db = None

        # 5. Connect via Paramiko
        await websocket.send_text(f"Connecting to {vm.hostname} ({vm.ip_address}:{vm.ssh_port})...\\r\\n")
        
        # Connection can take time, run in thread to avoid blocking event loop
        def _connect():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if credential.auth_type == 'ssh_key':
                key_file = StringIO(decrypted_credential)
                key_classes = [paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key]
                if hasattr(paramiko, 'DSSKey'):
                    key_classes.insert(1, paramiko.DSSKey)
                
                private_key = None
                for key_class in key_classes:
                    try:
                        key_file.seek(0)
                        private_key = key_class.from_private_key(key_file)
                        break
                    except paramiko.SSHException:
                        continue
                
                if private_key is None:
                    raise Exception("Failed to load SSH private key")
                    
                client.connect(
                    hostname=vm.ip_address,
                    port=vm.ssh_port,
                    username=credential.ssh_username,
                    pkey=private_key,
                    timeout=10,
                )
            else:
                client.connect(
                    hostname=vm.ip_address,
                    port=vm.ssh_port,
                    username=credential.ssh_username,
                    password=decrypted_credential,
                    timeout=10,
                )
            
            # Request PTY and invoke shell
            channel = client.invoke_shell(term='xterm-256color', width=80, height=24)
            return client, channel

        try:
            client, channel = await asyncio.to_thread(_connect)
        except Exception as e:
            logger.error(f"SSH connection failed to {vm.ip_address}: {e}")
            await websocket.send_text(f"\\r\\n[Error: SSH connection failed: {e}]\\r\\n")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # 6. Start bridging the connection
        session_manager = SSHSessionManager(websocket, client, channel)
        session_manager.start_reader_thread()
        
        # Run consumer tasks concurrently
        await asyncio.gather(
            session_manager.consume_queue(),
            session_manager.consume_websocket()
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"SSH WebSocket error: {e}")
        try:
            await websocket.send_text(f"\\r\\n[Internal Error: {e}]\\r\\n")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        if session_manager:
            session_manager.close()
        if db:
            db.close()
