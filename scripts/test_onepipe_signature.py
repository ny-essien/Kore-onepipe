import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.triple_des import make_signature


def test_signature_known_values():
    request_ref = "req-12345"
    client_secret = "s3cr3t"
    # Compute expected via direct hashlib for verification
    expected = hashlib.md5(f"{request_ref};{client_secret}".encode("utf-8")).hexdigest().lower()

    sig = make_signature(request_ref, client_secret)
    assert sig == expected, f"Signature mismatch: {sig} != {expected}"
    print(f"✓ Signature matches expected: {sig}")


def test_signature_empty_values_raises():
    try:
        make_signature(None, "secret")
    except ValueError:
        print("✓ None request_ref raises ValueError")
    else:
        raise AssertionError("Expected ValueError for None request_ref")

    try:
        make_signature("req", None)
    except ValueError:
        print("✓ None client_secret raises ValueError")
    else:
        raise AssertionError("Expected ValueError for None client_secret")


if __name__ == "__main__":
    try:
        test_signature_known_values()
        test_signature_empty_values_raises()
        print("\n✓ All signature tests passed")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise
