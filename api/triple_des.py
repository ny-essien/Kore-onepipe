"""
TripleDES encryption compatible with OnePipe Java code.

Implements DESede/CBC/PKCS5Padding encryption with:
- UTF-16LE plaintext encoding
- MD5-derived 24-byte key
- 8-byte zero IV
- Base64 output

Must match Java implementation for:
- auth.secure field
- meta.bvn field
"""

import hashlib
import base64
from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad


def derive_3des_key(secret: str) -> bytes:
    """
    Derive a 24-byte TripleDES key from a secret string.
    
    Process (matches Java):
    1. Encode secret as UTF-16LE bytes
    2. Compute MD5 hash of those bytes
    3. Take first 16 bytes of MD5
    4. Extend to 24 bytes by appending first 8 bytes of MD5 again
    
    Args:
        secret: Secret key string
        
    Returns:
        24-byte key suitable for DES3
    """
    # Encode secret as UTF-16LE
    secret_bytes = secret.encode('utf-16-le')
    
    # Compute MD5 digest
    md5_digest = hashlib.md5(secret_bytes).digest()  # 16 bytes
    
    # Extend to 24 bytes: first 16 bytes + first 8 bytes
    key_24 = md5_digest[:16] + md5_digest[:8]
    
    return key_24


def triple_des_encrypt(plaintext: str, secret: str) -> str:
    """
    Encrypt plaintext using TripleDES/CBC/PKCS5Padding.
    
    Process (matches Java):
    1. Encode plaintext as UTF-16LE bytes
    2. Derive 24-byte key from secret
    3. Create DES3 cipher in CBC mode with 8-byte zero IV
    4. Pad plaintext with PKCS5 (same as PKCS7 for 8-byte blocks)
    5. Encrypt
    6. Return base64 of ciphertext
    
    Args:
        plaintext: Text to encrypt
        secret: Secret key
        
    Returns:
        Base64-encoded ciphertext string
        
    Raises:
        ValueError: If inputs are invalid
    """
    if not plaintext:
        raise ValueError("Plaintext cannot be empty")
    if not secret:
        raise ValueError("Secret cannot be empty")
    
    # Encode plaintext as UTF-16LE
    plaintext_bytes = plaintext.encode('utf-16-le')
    
    # Derive key
    key = derive_3des_key(secret)
    
    # Create cipher with 8-byte zero IV
    iv = b'\x00' * 8
    cipher = DES3.new(key, DES3.MODE_CBC, iv)
    
    # Pad plaintext (PKCS5 is same as PKCS7 for 8-byte blocks)
    padded = pad(plaintext_bytes, 8, style='pkcs7')
    
    # Encrypt
    ciphertext = cipher.encrypt(padded)
    
    # Return base64
    return base64.b64encode(ciphertext).decode('ascii')


def triple_des_decrypt(ciphertext_b64: str, secret: str) -> str:
    """
    Decrypt a base64-encoded TripleDES ciphertext (for testing/verification).
    
    Args:
        ciphertext_b64: Base64-encoded ciphertext
        secret: Secret key
        
    Returns:
        Decrypted plaintext string
    """
    from Crypto.Util.Padding import unpad
    
    if not ciphertext_b64:
        raise ValueError("Ciphertext cannot be empty")
    if not secret:
        raise ValueError("Secret cannot be empty")
    
    # Decode base64
    ciphertext = base64.b64decode(ciphertext_b64)
    
    # Derive key
    key = derive_3des_key(secret)
    
    # Create cipher with 8-byte zero IV
    iv = b'\x00' * 8
    cipher = DES3.new(key, DES3.MODE_CBC, iv)
    
    # Decrypt
    padded_plaintext = cipher.decrypt(ciphertext)
    
    # Unpad
    plaintext_bytes = unpad(padded_plaintext, 8, style='pkcs7')
    
    # Decode UTF-16LE
    return plaintext_bytes.decode('utf-16-le')


def make_signature(request_ref: str, client_secret: str) -> str:
    """
    Create OnePipe signature: md5("{request_ref};{client_secret}") using UTF-8 encoding.

    Returns lowercase hex digest string.
    """
    if request_ref is None or client_secret is None:
        raise ValueError("request_ref and client_secret must be provided")

    to_hash = f"{request_ref};{client_secret}".encode("utf-8")
    return hashlib.md5(to_hash).hexdigest().lower()
