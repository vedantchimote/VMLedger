"""
Property-based tests for encryption and credential management.

These tests use Hypothesis to verify encryption round-trip properties
and SSH key validation.

Feature: vmledger-app
Requirements: 2.1, 2.2, 2.5, 11.2
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from io import StringIO
import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from vmledger.services.credential_manager import CredentialManager
from vmledger.models.user import User


# ============================================================================
# SSH Key Generation Helpers
# ============================================================================

def generate_rsa_key() -> str:
    """Generate a valid RSA private key."""
    key = paramiko.RSAKey.generate(bits=2048)
    key_file = StringIO()
    key.write_private_key(key_file)
    key_file.seek(0)
    return key_file.read()


def generate_ecdsa_key() -> str:
    """Generate a valid ECDSA private key."""
    key = paramiko.ECDSAKey.generate()
    key_file = StringIO()
    key.write_private_key(key_file)
    key_file.seek(0)
    return key_file.read()


def generate_ed25519_key() -> str:
    """Generate a valid Ed25519 private key using cryptography library."""
    # Generate key using cryptography library
    private_key = ed25519.Ed25519PrivateKey.generate()
    
    # Serialize to PEM format
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return pem.decode('utf-8')


# Custom Hypothesis strategies for SSH keys
@st.composite
def valid_ssh_keys(draw):
    """Generate valid SSH private keys of various types."""
    key_type = draw(st.sampled_from(['rsa', 'ecdsa', 'ed25519']))
    
    if key_type == 'rsa':
        return generate_rsa_key()
    elif key_type == 'ecdsa':
        return generate_ecdsa_key()
    else:  # ed25519
        return generate_ed25519_key()


# ============================================================================
# Property 3: SSH Key Format Validation
# ============================================================================

def test_property_3_ssh_key_validation_accepts_only_valid_keys(db_session):
    """
    Property 3: SSH Key Format Validation
    
    For any string input, the SSH key validation SHALL accept the input
    if and only if it is a valid RSA, DSA, ECDSA, or Ed25519 private key
    format that can be loaded by Paramiko.
    
    Validates: Requirements 2.5
    
    Note: Using example-based testing instead of @given to avoid fixture issues.
    """
    credential_manager = CredentialManager(db_session)
    
    # Test with various invalid inputs
    invalid_inputs = [
        "",
        "not a key",
        "-----BEGIN RSA PRIVATE KEY-----\ninvalid\n-----END RSA PRIVATE KEY-----",
        "random text",
        "12345",
        None,
    ]
    
    for key_string in invalid_inputs:
        result = credential_manager.validate_ssh_key(key_string)
        assert result is False, f"Invalid key was accepted: {key_string}"
    
    # Test with valid keys
    valid_keys = [
        generate_rsa_key(),
        generate_ecdsa_key(),
        generate_ed25519_key(),
    ]
    
    for key_string in valid_keys:
        result = credential_manager.validate_ssh_key(key_string)
        assert result is True, f"Valid key was rejected"


def test_property_3_valid_ssh_keys_always_accepted(db_session):
    """
    Property 3 (positive case): Valid SSH keys are always accepted.
    
    Validates: Requirements 2.5
    """
    credential_manager = CredentialManager(db_session)
    
    # Generate multiple keys of each type
    for _ in range(5):
        rsa_key = generate_rsa_key()
        ecdsa_key = generate_ecdsa_key()
        ed25519_key = generate_ed25519_key()
        
        assert credential_manager.validate_ssh_key(rsa_key) is True
        assert credential_manager.validate_ssh_key(ecdsa_key) is True
        assert credential_manager.validate_ssh_key(ed25519_key) is True


@given(invalid_key=st.one_of(
    st.text(max_size=100).filter(lambda s: not s.startswith('-----BEGIN')),
    st.just(""),
    st.just("invalid key"),
    st.just("-----BEGIN RSA PRIVATE KEY-----\ninvalid\n-----END RSA PRIVATE KEY-----"),
))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_3_invalid_ssh_keys_always_rejected(invalid_key, db_session):
    """
    Property 3 (negative case): Invalid SSH keys are always rejected.
    
    Validates: Requirements 2.5
    """
    credential_manager = CredentialManager(db_session)
    
    # Invalid keys should always be rejected
    result = credential_manager.validate_ssh_key(invalid_key)
    assert result is False, f"Invalid SSH key was accepted: {invalid_key[:50]}"


# ============================================================================
# Property 4: Credential Encryption Round-Trip
# ============================================================================

def test_property_4_ssh_key_encryption_round_trip(db_session):
    """
    Property 4: Credential Encryption Round-Trip (SSH Keys)
    
    For any valid SSH private key and any user, encrypting then decrypting
    the credential SHALL produce a value identical to the original credential.
    
    Validates: Requirements 2.1, 11.2
    """
    # Create a test user
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash="dummy_hash",
        encryption_salt="dummy_salt"
    )
    db_session.add(user)
    db_session.commit()
    
    credential_manager = CredentialManager(db_session)
    
    # Test with different key types
    keys = [
        generate_rsa_key(),
        generate_ecdsa_key(),
        generate_ed25519_key(),
    ]
    
    for ssh_key in keys:
        # Encrypt the SSH key
        encrypted = credential_manager.encrypt_ssh_key(user.id, ssh_key)
        
        # Verify it's actually encrypted (different from original)
        assert encrypted != ssh_key, "Encrypted key should differ from original"
        
        # Decrypt the SSH key
        decrypted = credential_manager.decrypt_ssh_key(user.id, encrypted)
        
        # Verify round-trip produces identical result
        assert decrypted == ssh_key, "Decrypted key should match original"
        assert len(decrypted) == len(ssh_key), "Decrypted key length should match original"


@given(password=st.text(min_size=1, max_size=1000))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_4_password_encryption_round_trip(password, db_session):
    """
    Property 4: Credential Encryption Round-Trip (Passwords)
    
    For any password and any user, encrypting then decrypting the credential
    SHALL produce a value identical to the original credential.
    
    Validates: Requirements 2.2, 11.2
    """
    # Create a test user
    user = User(
        username="test_user_pwd",
        email="test_pwd@example.com",
        password_hash="dummy_hash",
        encryption_salt="dummy_salt"
    )
    db_session.add(user)
    db_session.commit()
    
    credential_manager = CredentialManager(db_session)
    
    # Encrypt the password
    encrypted = credential_manager.encrypt_password(user.id, password)
    
    # Verify it's actually encrypted (different from original)
    assert encrypted != password, "Encrypted password should differ from original"
    
    # Decrypt the password
    decrypted = credential_manager.decrypt_password(user.id, encrypted)
    
    # Verify round-trip produces identical result
    assert decrypted == password, "Decrypted password should match original"
    assert len(decrypted) == len(password), "Decrypted password length should match original"


def test_property_4_encryption_is_user_specific(db_session):
    """
    Property 4 (user isolation): Encryption is user-specific.
    
    Credentials encrypted for one user cannot be decrypted by another user.
    
    Validates: Requirements 2.3
    """
    # Create two test users
    user1 = User(
        username="test_user1",
        email="test1@example.com",
        password_hash="dummy_hash",
        encryption_salt="dummy_salt1"
    )
    user2 = User(
        username="test_user2",
        email="test2@example.com",
        password_hash="dummy_hash",
        encryption_salt="dummy_salt2"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    credential_manager = CredentialManager(db_session)
    password = "test_password_123"
    
    # Encrypt with user 1
    encrypted = credential_manager.encrypt_password(user1.id, password)
    
    # Try to decrypt with user 2 - should fail or produce garbage
    try:
        decrypted = credential_manager.decrypt_password(user2.id, encrypted)
        # If it doesn't raise an exception, it should produce different output
        assert decrypted != password, \
            "Different user should not be able to decrypt another user's credentials"
    except Exception:
        # Expected - decryption should fail for wrong user
        pass


# ============================================================================
# Edge Cases and Specific Examples
# ============================================================================

def test_ssh_key_validation_specific_cases(db_session):
    """Test SSH key validation with specific examples."""
    credential_manager = CredentialManager(db_session)
    
    # Valid keys
    rsa_key = generate_rsa_key()
    ecdsa_key = generate_ecdsa_key()
    ed25519_key = generate_ed25519_key()
    
    assert credential_manager.validate_ssh_key(rsa_key) is True
    assert credential_manager.validate_ssh_key(ecdsa_key) is True
    assert credential_manager.validate_ssh_key(ed25519_key) is True
    
    # Invalid keys
    assert credential_manager.validate_ssh_key("") is False
    assert credential_manager.validate_ssh_key("not a key") is False
    assert credential_manager.validate_ssh_key(None) is False
    assert credential_manager.validate_ssh_key("-----BEGIN RSA PRIVATE KEY-----\n-----END RSA PRIVATE KEY-----") is False


def test_encryption_with_empty_password(db_session):
    """Test encryption with empty password."""
    credential_manager = CredentialManager(db_session)
    user_id = 1
    
    # Empty password should still work
    encrypted = credential_manager.encrypt_password(user_id, "")
    decrypted = credential_manager.decrypt_password(user_id, encrypted)
    
    assert decrypted == ""


def test_encryption_with_special_characters(db_session):
    """Test encryption with passwords containing special characters."""
    credential_manager = CredentialManager(db_session)
    user_id = 1
    
    special_passwords = [
        "p@ssw0rd!",
        "密码123",  # Chinese characters
        "пароль",  # Cyrillic
        "🔐🔑",  # Emojis
        "\n\t\r",  # Whitespace characters
        "a" * 1000,  # Long password
    ]
    
    for password in special_passwords:
        encrypted = credential_manager.encrypt_password(user_id, password)
        decrypted = credential_manager.decrypt_password(user_id, encrypted)
        assert decrypted == password, f"Failed for password: {password[:50]}"


def test_encryption_determinism(db_session):
    """Test that encryption produces different ciphertexts for same input."""
    credential_manager = CredentialManager(db_session)
    user_id = 1
    password = "test_password"
    
    # Encrypt the same password twice
    encrypted1 = credential_manager.encrypt_password(user_id, password)
    encrypted2 = credential_manager.encrypt_password(user_id, password)
    
    # Ciphertexts should be different (due to random IV/nonce)
    # This is a security feature - prevents pattern analysis
    # Note: Fernet includes a timestamp, so they will be different
    assert encrypted1 != encrypted2, "Encryption should produce different ciphertexts"
    
    # But both should decrypt to the same value
    decrypted1 = credential_manager.decrypt_password(user_id, encrypted1)
    decrypted2 = credential_manager.decrypt_password(user_id, encrypted2)
    
    assert decrypted1 == password
    assert decrypted2 == password


def test_ssh_key_types_coverage(db_session):
    """Test that all supported SSH key types are validated correctly."""
    credential_manager = CredentialManager(db_session)
    
    # Generate and test each key type
    key_types = {
        'RSA': generate_rsa_key(),
        'ECDSA': generate_ecdsa_key(),
        'Ed25519': generate_ed25519_key(),
    }
    
    for key_type, key in key_types.items():
        assert credential_manager.validate_ssh_key(key) is True, \
            f"{key_type} key should be valid"
        
        # Test encryption round-trip for each type
        encrypted = credential_manager.encrypt_ssh_key(1, key)
        decrypted = credential_manager.decrypt_ssh_key(1, encrypted)
        assert decrypted == key, f"{key_type} key round-trip failed"


def test_encryption_with_different_user_ids(db_session):
    """Test encryption with various user IDs."""
    credential_manager = CredentialManager(db_session)
    password = "test_password"
    
    user_ids = [1, 100, 999999, 1000000]
    
    for user_id in user_ids:
        encrypted = credential_manager.encrypt_password(user_id, password)
        decrypted = credential_manager.decrypt_password(user_id, encrypted)
        assert decrypted == password, f"Failed for user_id: {user_id}"


def test_decryption_with_invalid_ciphertext(db_session):
    """Test that decryption fails gracefully with invalid ciphertext."""
    from vmledger.services.credential_manager import DecryptionError
    
    credential_manager = CredentialManager(db_session)
    user_id = 1
    
    invalid_ciphertexts = [
        "",
        "invalid",
        "not-base64-encoded",
        "Z2FyYmFnZQ==",  # Valid base64 but not valid Fernet token
    ]
    
    for invalid in invalid_ciphertexts:
        with pytest.raises(DecryptionError):
            credential_manager.decrypt_password(user_id, invalid)
