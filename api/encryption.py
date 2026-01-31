"""
Encryption utilities for sensitive fields (account numbers, BVN, etc.).
Uses ONEPIPE_CLIENT_SECRET to derive a Fernet key via SHA256.
Never logs plaintext values.
"""
import hashlib
import base64
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def _get_encryption_key():
    """
    Derive a Fernet-compatible key from ONEPIPE_CLIENT_SECRET.
    Uses SHA256 hashing and base64 urlsafe encoding.
    """
    secret = settings.ONEPIPE.get("CLIENT_SECRET", "")
    if not secret:
        raise ValueError("ONEPIPE_CLIENT_SECRET not configured in settings")
    
    # Hash the secret with SHA256
    hash_bytes = hashlib.sha256(secret.encode()).digest()
    
    # Base64 urlsafe encode for Fernet compatibility (32 bytes required)
    key = base64.urlsafe_b64encode(hash_bytes)
    return key


def encrypt_value(plaintext):
    """
    Encrypt a plaintext string using Fernet.
    
    Args:
        plaintext (str or None): The value to encrypt
        
    Returns:
        str: Base64-encoded encrypted value, or empty string if input is None/empty
        
    Raises:
        ValueError: If encryption key cannot be derived
    """
    if not plaintext:
        return ""
    
    try:
        key = _get_encryption_key()
        cipher = Fernet(key)
        # Encode plaintext to bytes, encrypt, then decode to string
        ciphertext = cipher.encrypt(plaintext.encode())
        return ciphertext.decode()
    except Exception as e:
        raise ValueError(f"Encryption failed: {str(e)}")


def decrypt_value(ciphertext):
    """
    Decrypt a Fernet-encrypted ciphertext.
    
    Args:
        ciphertext (str or None): The encrypted value to decrypt
        
    Returns:
        str: Decrypted plaintext, or empty string if input is None/empty
        
    Raises:
        ValueError: If decryption fails (invalid ciphertext or key mismatch)
    """
    if not ciphertext:
        return ""
    
    try:
        key = _get_encryption_key()
        cipher = Fernet(key)
        # Decode ciphertext string to bytes, decrypt, then decode to string
        plaintext = cipher.decrypt(ciphertext.encode())
        return plaintext.decode()
    except InvalidToken:
        raise ValueError("Decryption failed: invalid token or corrupted data")
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
