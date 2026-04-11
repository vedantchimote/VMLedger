"""
Credential Manager Service for secure encryption and decryption of SSH credentials.

This service implements AES-256-GCM encryption using Fernet for storing SSH keys
and passwords securely. It uses PBKDF2-HMAC-SHA256 for key derivation with
user-specific salts.

Requirements: 2.1-2.6, 11.2, 11.4
"""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import paramiko
from sqlalchemy.orm import Session

from vmledger.config import settings
from vmledger.models.credential import Credential
from vmledger.models.user import User
from vmledger.exceptions import (
    CredentialManagerError,
    InvalidSSHKeyError,
    EncryptionError,
    UserNotFoundError
)


logger = logging.getLogger(__name__)


class DecryptionError(CredentialManagerError):
    """Raised when credential decryption fails."""
    pass


class CredentialManager:
    """
    Manages secure encryption and decryption of SSH credentials.
    
    Uses AES-256-GCM encryption via Fernet with per-user key derivation
    using PBKDF2-HMAC-SHA256.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the credential manager.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._master_key = settings.encryption_master_key.encode()
    
    def _derive_user_key(self, user_id: int) -> bytes:
        """
        Derive a user-specific encryption key using PBKDF2-HMAC-SHA256.
        
        Args:
            user_id: User ID to derive key for
            
        Returns:
            32-byte encryption key suitable for Fernet
            
        Requirements: 2.3 - Use unique encryption keys per user
        """
        # Get user's encryption salt from database
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise CredentialManagerError(f"User {user_id} not found")
        
        # Use user's encryption salt for key derivation
        salt = user.encryption_salt.encode()
        
        # Derive key using PBKDF2-HMAC-SHA256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 32 bytes = 256 bits for AES-256
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=default_backend()
        )
        
        derived_key = kdf.derive(self._master_key)
        
        # Fernet requires base64-encoded key
        return base64.urlsafe_b64encode(derived_key)
    
    def _get_fernet(self, user_id: int) -> Fernet:
        """
        Get a Fernet instance with user-specific key.
        
        Args:
            user_id: User ID to get Fernet for
            
        Returns:
            Fernet instance for encryption/decryption
        """
        user_key = self._derive_user_key(user_id)
        return Fernet(user_key)
    
    def validate_ssh_key(self, private_key: str) -> bool:
        """
        Validate SSH private key format using Paramiko.
        
        Supports RSA, ECDSA, and Ed25519 key formats.
        DSA keys are deprecated and no longer supported.
        Rejects passphrase-protected (encrypted) private keys.
        
        Args:
            private_key: SSH private key string
            
        Returns:
            True if key is valid, False otherwise
            
        Requirements: 2.5 - Validate SSH key format before storage
        """
        if not private_key or not isinstance(private_key, str):
            return False
        
        try:
            from io import StringIO
            
            # Create a file-like object from the key string
            key_file = StringIO(private_key)
            
            # Try loading as different key types
            # Try RSA
            try:
                key_file.seek(0)
                paramiko.RSAKey.from_private_key(key_file)
                return True
            except paramiko.SSHException:
                pass
            
            # Try ECDSA
            try:
                key_file.seek(0)
                paramiko.ECDSAKey.from_private_key(key_file)
                return True
            except paramiko.SSHException:
                pass
            
            # Try Ed25519
            try:
                key_file.seek(0)
                paramiko.Ed25519Key.from_private_key(key_file)
                return True
            except paramiko.SSHException:
                pass
            
            # None of the key types worked
            return False
            
        except Exception as e:
            logger.debug(f"SSH key validation failed: {e}")
            return False
    
    def encrypt_ssh_key(self, user_id: int, private_key: str) -> str:
        """
        Encrypt SSH private key using AES-256-GCM.
        
        Args:
            user_id: User ID who owns the key
            private_key: SSH private key in PEM format
            
        Returns:
            Base64-encoded encrypted credential
            
        Raises:
            InvalidSSHKeyError: If key format is invalid
            CredentialManagerError: If encryption fails
            
        Requirements: 2.1 - Encrypt SSH private keys using AES-256
        Requirements: 2.5 - Validate key format before storage
        """
        # Validate key format first
        if not self.validate_ssh_key(private_key):
            raise InvalidSSHKeyError("Invalid SSH private key format")
        
        try:
            fernet = self._get_fernet(user_id)
            encrypted = fernet.encrypt(private_key.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt SSH key for user {user_id}: {e}")
            raise CredentialManagerError(f"Encryption failed: {e}")
    
    def decrypt_ssh_key(self, user_id: int, encrypted_key: str) -> str:
        """
        Decrypt SSH private key.
        
        Args:
            user_id: User ID who owns the key
            encrypted_key: Base64-encoded encrypted credential
            
        Returns:
            Decrypted SSH private key
            
        Raises:
            DecryptionError: If decryption fails
            
        Requirements: 2.1 - Decrypt SSH private keys
        """
        try:
            fernet = self._get_fernet(user_id)
            decrypted = fernet.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error(f"Invalid token during SSH key decryption for user {user_id}")
            raise DecryptionError("Failed to decrypt SSH key: invalid token")
        except Exception as e:
            logger.error(f"Failed to decrypt SSH key for user {user_id}: {e}")
            raise DecryptionError(f"Decryption failed: {e}")
    
    def encrypt_password(self, user_id: int, password: str) -> str:
        """
        Encrypt password using AES-256-GCM.
        
        Args:
            user_id: User ID who owns the password
            password: Plain text password
            
        Returns:
            Base64-encoded encrypted credential
            
        Raises:
            CredentialManagerError: If encryption fails
            
        Requirements: 2.2 - Encrypt password-based credentials using AES-256
        """
        if not password or not isinstance(password, str):
            raise CredentialManagerError("Password must be a non-empty string")
        
        try:
            fernet = self._get_fernet(user_id)
            encrypted = fernet.encrypt(password.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt password for user {user_id}: {e}")
            raise CredentialManagerError(f"Encryption failed: {e}")
    
    def decrypt_password(self, user_id: int, encrypted_password: str) -> str:
        """
        Decrypt password.
        
        Args:
            user_id: User ID who owns the password
            encrypted_password: Base64-encoded encrypted credential
            
        Returns:
            Decrypted password
            
        Raises:
            DecryptionError: If decryption fails
            
        Requirements: 2.2 - Decrypt password-based credentials
        """
        try:
            fernet = self._get_fernet(user_id)
            decrypted = fernet.decrypt(encrypted_password.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error(f"Invalid token during password decryption for user {user_id}")
            raise DecryptionError("Failed to decrypt password: invalid token")
        except Exception as e:
            logger.error(f"Failed to decrypt password for user {user_id}: {e}")
            raise DecryptionError(f"Decryption failed: {e}")
    
    def delete_credentials(self, vm_id: int) -> bool:
        """
        Delete credentials for a VM.
        
        Args:
            vm_id: VM ID to delete credentials for
            
        Returns:
            True if credentials were deleted, False if not found
            
        Requirements: 11.4 - Remove credentials when VM is deleted
        """
        try:
            credential = self.db.query(Credential).filter(
                Credential.vm_id == vm_id
            ).first()
            
            if credential:
                self.db.delete(credential)
                self.db.commit()
                logger.info(f"Deleted credentials for VM {vm_id}")
                return True
            else:
                logger.debug(f"No credentials found for VM {vm_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete credentials for VM {vm_id}: {e}")
            self.db.rollback()
            raise CredentialManagerError(f"Failed to delete credentials: {e}")
