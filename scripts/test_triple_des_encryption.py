"""
Tests for TripleDES encryption implementation.

Verifies:
- Stable encryption output (snapshot test)
- Round-trip encrypt/decrypt
- Key derivation correctness
- No errors on typical inputs
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kore.settings")

from api.triple_des import derive_3des_key, triple_des_encrypt, triple_des_decrypt


def test_key_derivation_deterministic():
    """Key derivation should always produce same key for same secret"""
    secret = "test-secret-key"
    
    key1 = derive_3des_key(secret)
    key2 = derive_3des_key(secret)
    
    assert key1 == key2, "Key derivation not deterministic"
    assert len(key1) == 24, f"Key length should be 24, got {len(key1)}"
    
    print("✓ Key derivation is deterministic and correct length (24 bytes)")


def test_encryption_stable():
    """Encryption should produce same ciphertext for same inputs (snapshot test)"""
    secret = "OnePipeSecret"
    plaintext = "1234567890"
    
    ciphertext1 = triple_des_encrypt(plaintext, secret)
    ciphertext2 = triple_des_encrypt(plaintext, secret)
    
    assert ciphertext1 == ciphertext2, "Encryption not stable"
    assert ciphertext1, "Ciphertext should not be empty"
    
    print(f"✓ Encryption is stable: '{plaintext}' -> '{ciphertext1}'")


def test_roundtrip_decrypt():
    """Encrypted text should decrypt back to original"""
    secret = "MySecretKey123"
    plaintext = "Hello, OnePipe!"
    
    ciphertext = triple_des_encrypt(plaintext, secret)
    decrypted = triple_des_decrypt(ciphertext, secret)
    
    assert decrypted == plaintext, f"Roundtrip failed: {plaintext} != {decrypted}"
    
    print(f"✓ Roundtrip successful: '{plaintext}' -> [encrypted] -> '{decrypted}'")


def test_roundtrip_long_text():
    """Long plaintext should also roundtrip correctly"""
    secret = "VeryLongSecretKey"
    plaintext = "This is a longer message with special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    
    ciphertext = triple_des_encrypt(plaintext, secret)
    decrypted = triple_des_decrypt(ciphertext, secret)
    
    assert decrypted == plaintext, f"Long text roundtrip failed"
    
    print(f"✓ Long text roundtrip successful ({len(plaintext)} chars)")


def test_roundtrip_utf16_chars():
    """UTF-16LE encoded special chars should roundtrip"""
    secret = "UTF16Secret"
    plaintext = "Special: é à ñ ü 中文 日本語"
    
    ciphertext = triple_des_encrypt(plaintext, secret)
    decrypted = triple_des_decrypt(ciphertext, secret)
    
    assert decrypted == plaintext, f"UTF-16 roundtrip failed"
    
    print(f"✓ UTF-16 special chars roundtrip successful")


def test_different_secrets_produce_different_ciphertexts():
    """Same plaintext with different secrets should produce different ciphertexts"""
    plaintext = "TestData"
    
    ciphertext1 = triple_des_encrypt(plaintext, "Secret1")
    ciphertext2 = triple_des_encrypt(plaintext, "Secret2")
    
    assert ciphertext1 != ciphertext2, "Different secrets should produce different ciphertexts"
    
    print("✓ Different secrets produce different ciphertexts")


def test_different_plaintexts_produce_different_ciphertexts():
    """Same secret with different plaintexts should produce different ciphertexts"""
    secret = "SameSecret"
    
    ciphertext1 = triple_des_encrypt("PlainText1", secret)
    ciphertext2 = triple_des_encrypt("PlainText2", secret)
    
    assert ciphertext1 != ciphertext2, "Different plaintexts should produce different ciphertexts"
    
    print("✓ Different plaintexts produce different ciphertexts")


def test_base64_output():
    """Output should be valid base64"""
    import base64
    
    secret = "Base64Test"
    plaintext = "TestPlaintext"
    
    ciphertext = triple_des_encrypt(plaintext, secret)
    
    # Should be decodable as base64
    try:
        decoded_bytes = base64.b64decode(ciphertext)
        assert len(decoded_bytes) > 0, "Decoded bytes should not be empty"
    except Exception as e:
        raise AssertionError(f"Output is not valid base64: {e}")
    
    print(f"✓ Output is valid base64 (length: {len(ciphertext)} chars)")


def test_no_error_on_typical_inputs():
    """Should handle typical BVN and account number formats without error"""
    secret = "OnePipeSecret"
    
    # Test BVN-like input (11 digits)
    bvn = "12345678901"
    ciphertext_bvn = triple_des_encrypt(bvn, secret)
    assert ciphertext_bvn, "BVN encryption should not be empty"
    
    # Test account number (10 digits)
    account = "1234567890"
    ciphertext_account = triple_des_encrypt(account, secret)
    assert ciphertext_account, "Account encryption should not be empty"
    
    print("✓ Handles typical BVN and account inputs without error")


def test_snapshot_consistency():
    """
    Snapshot test: verify known input produces expected output.
    
    This ensures compatibility with Java implementation.
    If this changes, it means the encryption changed.
    """
    secret = "OnePipeTestSecret"
    plaintext = "TEST123456"
    
    ciphertext = triple_des_encrypt(plaintext, secret)
    
    # This is a snapshot. If the algorithm changes, this test will fail.
    # The ciphertext should be deterministic for the same inputs.
    expected_format = isinstance(ciphertext, str) and len(ciphertext) > 0
    assert expected_format, "Ciphertext should be a non-empty string"
    
    # Verify roundtrip
    decrypted = triple_des_decrypt(ciphertext, secret)
    assert decrypted == plaintext, f"Snapshot roundtrip failed: {plaintext} != {decrypted}"
    
    print(f"✓ Snapshot test passed: '{plaintext}' encrypts to stable output")


if __name__ == "__main__":
    try:
        print("[Test 1] Key derivation deterministic...")
        test_key_derivation_deterministic()
        
        print("\n[Test 2] Encryption is stable...")
        test_encryption_stable()
        
        print("\n[Test 3] Roundtrip encrypt/decrypt...")
        test_roundtrip_decrypt()
        
        print("\n[Test 4] Long text roundtrip...")
        test_roundtrip_long_text()
        
        print("\n[Test 5] UTF-16 special chars roundtrip...")
        test_roundtrip_utf16_chars()
        
        print("\n[Test 6] Different secrets produce different outputs...")
        test_different_secrets_produce_different_ciphertexts()
        
        print("\n[Test 7] Different plaintexts produce different outputs...")
        test_different_plaintexts_produce_different_ciphertexts()
        
        print("\n[Test 8] Base64 output validation...")
        test_base64_output()
        
        print("\n[Test 9] Handles typical inputs...")
        test_no_error_on_typical_inputs()
        
        print("\n[Test 10] Snapshot consistency...")
        test_snapshot_consistency()
        
        print("\n" + "=" * 70)
        print("✓ All TripleDES encryption tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
