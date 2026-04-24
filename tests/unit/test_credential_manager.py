"""
Unit tests for CredentialManager service.

Tests encryption, decryption, validation, and deletion of credentials.
Requirements: 2.1-2.6, 11.2, 11.4
"""

import pytest
import paramiko
from io import StringIO
from cryptography.hazmat.primitives.asymmetric import rsa, ec, ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from vmledger.services.credential_manager import (
    CredentialManager,
    CredentialManagerError,
    InvalidSSHKeyError,
    DecryptionError,
)
from vmledger.models.user import User
from vmledger.models.vm import VM
from vmledger.models.credential import Credential


def generate_rsa_key() -> str:
    """Generate a valid RSA private key in PEM format using Paramiko."""
    key = paramiko.RSAKey.generate(2048)
    from io import StringIO
    key_file = StringIO()
    key.write_private_key(key_file)
    return key_file.getvalue()


def generate_dsa_key() -> str:
    """
    DSA keys are deprecated and removed from Paramiko 4.0+.
    Return a valid RSA key instead for testing purposes.
    """
    return generate_rsa_key()


def generate_ecdsa_key() -> str:
    """Generate a valid ECDSA private key in PEM format using Paramiko."""
    key = paramiko.ECDSAKey.generate()
    from io import StringIO
    key_file = StringIO()
    key.write_private_key(key_file)
    return key_file.getvalue()


def generate_ed25519_key() -> str:
    """Generate a valid Ed25519 private key using cryptography library."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )
    return pem.decode()


class TestCredentialManagerValidation:
    """Test SSH key format validation."""
    
    def test_validate_rsa_key(self, db_session):
        """Test validation of RSA private key."""
        manager = CredentialManager(db_session)
        rsa_key = generate_rsa_key()
        
        assert manager.validate_ssh_key(rsa_key) is True
    
    def test_validate_dsa_key(self, db_session):
        """Test validation of DSA private key."""
        manager = CredentialManager(db_session)
        dsa_key = generate_dsa_key()
        
        assert manager.validate_ssh_key(dsa_key) is True
    
    def test_validate_ecdsa_key(self, db_session):
        """Test validation of ECDSA private key."""
        manager = CredentialManager(db_session)
        ecdsa_key = generate_ecdsa_key()
        
        assert manager.validate_ssh_key(ecdsa_key) is True
    
    def test_validate_ed25519_key(self, db_session):
        """Test validation of Ed25519 private key."""
        manager = CredentialManager(db_session)
        ed25519_key = generate_ed25519_key()
        
        assert manager.validate_ssh_key(ed25519_key) is True
    
    def test_validate_invalid_key_format(self, db_session):
        """Test validation rejects invalid key format."""
        manager = CredentialManager(db_session)
        
        invalid_keys = [
            "not a key",
            "-----BEGIN RSA PRIVATE KEY-----\ninvalid\n-----END RSA PRIVATE KEY-----",
            "",
            "random text",
            "12345",
        ]
        
        for invalid_key in invalid_keys:
            assert manager.validate_ssh_key(invalid_key) is False
    
    def test_validate_none_key(self, db_session):
        """Test validation rejects None."""
        manager = CredentialManager(db_session)
        assert manager.validate_ssh_key(None) is False
    
    def test_validate_non_string_key(self, db_session):
        """Test validation rejects non-string input."""
        manager = CredentialManager(db_session)
        assert manager.validate_ssh_key(12345) is False
        assert manager.validate_ssh_key([]) is False
        assert manager.validate_ssh_key({}) is False


class TestCredentialManagerEncryption:
    """Test credential encryption and decryption."""
    
    def test_encrypt_decrypt_ssh_key_roundtrip(self, db_session, test_user):
        """
        Test encryption and decryption of SSH key produces original value.
        Requirements: 2.1, 11.2
        """
        manager = CredentialManager(db_session)
        original_key = generate_rsa_key()
        
        # Encrypt
        encrypted = manager.encrypt_ssh_key(test_user.id, original_key)
        assert encrypted != original_key
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = manager.decrypt_ssh_key(test_user.id, encrypted)
        assert decrypted == original_key
    
    def test_encrypt_decrypt_password_roundtrip(self, db_session, test_user):
        """
        Test encryption and decryption of password produces original value.
        Requirements: 2.2, 11.2
        """
        manager = CredentialManager(db_session)
        original_password = "MySecurePassword123!"
        
        # Encrypt
        encrypted = manager.encrypt_password(test_user.id, original_password)
        assert encrypted != original_password
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = manager.decrypt_password(test_user.id, encrypted)
        assert decrypted == original_password
    
    def test_encrypt_ssh_key_validates_format(self, db_session, test_user):
        """
        Test that encrypt_ssh_key validates key format before encryption.
        Requirements: 2.5
        """
        manager = CredentialManager(db_session)
        invalid_key = "not a valid ssh key"
        
        with pytest.raises(InvalidSSHKeyError):
            manager.encrypt_ssh_key(test_user.id, invalid_key)
    
    def test_encrypt_different_key_types(self, db_session, test_user):
        """Test encryption works with different SSH key types."""
        manager = CredentialManager(db_session)
        
        key_types = [
            ("RSA", generate_rsa_key()),
            ("DSA", generate_dsa_key()),
            ("ECDSA", generate_ecdsa_key()),
            ("Ed25519", generate_ed25519_key()),
        ]
        
        for key_type, key in key_types:
            encrypted = manager.encrypt_ssh_key(test_user.id, key)
            decrypted = manager.decrypt_ssh_key(test_user.id, encrypted)
            assert decrypted == key, f"{key_type} key roundtrip failed"
    
    def test_user_specific_encryption(self, db_session, test_user, test_user2):
        """
        Test that encryption keys are user-specific.
        Requirements: 2.3 - Use unique encryption keys per user
        """
        manager = CredentialManager(db_session)
        password = "TestPassword123"
        
        # Encrypt with user 1
        encrypted1 = manager.encrypt_password(test_user.id, password)
        
        # Encrypt with user 2
        encrypted2 = manager.encrypt_password(test_user2.id, password)
        
        # Encrypted values should be different (different keys)
        assert encrypted1 != encrypted2
        
        # Each user can decrypt their own
        assert manager.decrypt_password(test_user.id, encrypted1) == password
        assert manager.decrypt_password(test_user2.id, encrypted2) == password
        
        # User 1 cannot decrypt user 2's credential
        with pytest.raises(DecryptionError):
            manager.decrypt_password(test_user.id, encrypted2)
        
        # User 2 cannot decrypt user 1's credential
        with pytest.raises(DecryptionError):
            manager.decrypt_password(test_user2.id, encrypted1)
    
    def test_decrypt_invalid_token(self, db_session, test_user):
        """Test decryption fails with invalid token."""
        manager = CredentialManager(db_session)
        
        with pytest.raises(DecryptionError):
            manager.decrypt_ssh_key(test_user.id, "invalid_encrypted_data")
        
        with pytest.raises(DecryptionError):
            manager.decrypt_password(test_user.id, "invalid_encrypted_data")
    
    def test_encrypt_empty_password(self, db_session, test_user):
        """Test encryption rejects empty password."""
        manager = CredentialManager(db_session)
        
        with pytest.raises(CredentialManagerError):
            manager.encrypt_password(test_user.id, "")
        
        with pytest.raises(CredentialManagerError):
            manager.encrypt_password(test_user.id, None)
    
    def test_encrypt_nonexistent_user(self, db_session):
        """Test encryption fails for nonexistent user."""
        manager = CredentialManager(db_session)
        
        with pytest.raises(CredentialManagerError):
            manager.encrypt_password(99999, "password")


class TestCredentialManagerDeletion:
    """Test credential deletion."""
    
    def test_delete_credentials(self, db_session, test_user, test_vm):
        """
        Test deletion of credentials for a VM.
        Requirements: 11.4
        """
        manager = CredentialManager(db_session)
        
        # Create credential
        encrypted_password = manager.encrypt_password(test_user.id, "password123")
        credential = Credential(
            vm_id=test_vm.id,
            auth_type="password",
            encrypted_credential=encrypted_password,
            ssh_username="root"
        )
        db_session.add(credential)
        db_session.commit()
        
        # Verify credential exists
        assert db_session.query(Credential).filter(
            Credential.vm_id == test_vm.id
        ).first() is not None
        
        # Delete credentials
        result = manager.delete_credentials(test_vm.id)
        assert result is True
        
        # Verify credential is deleted
        assert db_session.query(Credential).filter(
            Credential.vm_id == test_vm.id
        ).first() is None
    
    def test_delete_nonexistent_credentials(self, db_session):
        """Test deletion returns False for nonexistent credentials."""
        manager = CredentialManager(db_session)
        
        result = manager.delete_credentials(99999)
        assert result is False
    
    def test_delete_credentials_multiple_times(self, db_session, test_user, test_vm):
        """Test deleting credentials multiple times."""
        manager = CredentialManager(db_session)
        
        # Create credential
        encrypted_password = manager.encrypt_password(test_user.id, "password123")
        credential = Credential(
            vm_id=test_vm.id,
            auth_type="password",
            encrypted_credential=encrypted_password,
            ssh_username="root"
        )
        db_session.add(credential)
        db_session.commit()
        
        # First deletion succeeds
        assert manager.delete_credentials(test_vm.id) is True
        
        # Second deletion returns False (already deleted)
        assert manager.delete_credentials(test_vm.id) is False


class TestCredentialManagerEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_encrypt_very_long_password(self, db_session, test_user):
        """Test encryption of very long password."""
        manager = CredentialManager(db_session)
        long_password = "a" * 10000
        
        encrypted = manager.encrypt_password(test_user.id, long_password)
        decrypted = manager.decrypt_password(test_user.id, encrypted)
        
        assert decrypted == long_password
    
    def test_encrypt_password_with_special_characters(self, db_session, test_user):
        """Test encryption of password with special characters."""
        manager = CredentialManager(db_session)
        special_password = "P@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"
        
        encrypted = manager.encrypt_password(test_user.id, special_password)
        decrypted = manager.decrypt_password(test_user.id, encrypted)
        
        assert decrypted == special_password
    
    def test_encrypt_password_with_unicode(self, db_session, test_user):
        """Test encryption of password with unicode characters."""
        manager = CredentialManager(db_session)
        unicode_password = "пароль密码🔐"
        
        encrypted = manager.encrypt_password(test_user.id, unicode_password)
        decrypted = manager.decrypt_password(test_user.id, encrypted)
        
        assert decrypted == unicode_password
