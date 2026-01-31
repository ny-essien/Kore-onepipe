#!/usr/bin/env python
"""
Test script for GET /api/banks/ endpoint.
Tests caching, error handling, and response format.
"""
import os
import sys
import django
import requests
import json
from unittest.mock import patch, MagicMock

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from rest_framework.test import APIClient
from django.core.cache import cache


def test_banks_endpoint_public():
    """Test that GET /api/banks/ is publicly accessible (no auth required)"""
    print("\n[TEST 1] Testing public access to GET /api/banks/...")
    
    client = APIClient()
    
    with patch('api.views.OnePipeClient') as mock_client_class:
        # Mock the OnePipe response
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.transact.return_value = {
            "request_ref": "test-123",
            "response": {
                "status": "Successful",
                "data": {
                    "banks": [
                        {"bank_name": "Access Bank", "bank_code": "044"},
                        {"bank_name": "GTBank", "bank_code": "058"},
                    ]
                }
            }
        }
        
        # Clear cache
        cache.delete("onepipe:get_banks")
        
        # Make request WITHOUT authentication
        response = client.get("/api/banks/")
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {json.dumps(response.json() if hasattr(response, 'json') else response.data, indent=2)}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Response is either a list or dict with "banks" key
        resp_data = response.json() if hasattr(response, 'json') else response.data
        if isinstance(resp_data, list):
            assert len(resp_data) == 2, f"Expected 2 banks, got {len(resp_data)}"
        else:
            assert "banks" in resp_data, "Response missing 'banks' key"
            assert len(resp_data["banks"]) == 2, "Expected 2 banks"
        
        print("  ✅ PASS: Public endpoint works, returns banks list")


def test_banks_endpoint_caching():
    """Test that GET /api/banks/ uses caching (3600s TTL)"""
    print("\n[TEST 2] Testing caching behavior...")
    
    client = APIClient()
    
    with patch('api.views.OnePipeClient') as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.transact.return_value = {
            "request_ref": "test-456",
            "response": {
                "status": "Successful",
                "data": {
                    "banks": [
                        {"bank_name": "First Bank", "bank_code": "011"},
                    ]
                }
            }
        }
        
        # Clear cache
        cache.delete("onepipe:get_banks")
        
        # First request - should call OnePipe
        response1 = client.get("/api/banks/")
        call_count_1 = mock_instance.transact.call_count
        
        # Second request - should use cache
        response2 = client.get("/api/banks/")
        call_count_2 = mock_instance.transact.call_count
        
        resp1_data = response1.json() if hasattr(response1, 'json') else response1.data
        resp2_data = response2.json() if hasattr(response2, 'json') else response2.data
        
        print(f"  First request transact calls: {call_count_1}")
        print(f"  Second request transact calls: {call_count_2}")
        print(f"  Response 1: {json.dumps(resp1_data, indent=2)}")
        print(f"  Response 2: {json.dumps(resp2_data, indent=2)}")
        
        assert call_count_1 == 1, f"Expected 1 transact call, got {call_count_1}"
        assert call_count_2 == 1, f"Expected cache to prevent 2nd call, but got {call_count_2}"
        assert resp1_data == resp2_data, "Cached responses should match"
        print("  ✅ PASS: Caching works correctly")


def test_banks_endpoint_error_handling():
    """Test that GET /api/banks/ handles OnePipe errors gracefully"""
    print("\n[TEST 3] Testing error handling...")
    
    client = APIClient()
    
    with patch('api.views.OnePipeClient') as mock_client_class:
        from api.onepipe_client import OnePipeError
        
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.transact.side_effect = OnePipeError(502, "Service Unavailable")
        
        # Clear cache
        cache.delete("onepipe:get_banks")
        
        response = client.get("/api/banks/")
        resp_data = response.json() if hasattr(response, 'json') else response.data
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {json.dumps(resp_data, indent=2)}")
        
        assert response.status_code == 502, f"Expected 502, got {response.status_code}"
        print("  ✅ PASS: Error handling returns 502 Bad Gateway")


def test_banks_endpoint_response_formats():
    """Test that GET /api/banks/ handles various OnePipe response formats"""
    print("\n[TEST 4] Testing response format variations...")
    
    client = APIClient()
    
    # Test with banks at response root
    with patch('api.views.OnePipeClient') as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.transact.return_value = {
            "request_ref": "test-789",
            "response": {
                "banks": [
                    {"bank_name": "Root Bank", "bank_code": "999"},
                ]
            }
        }
        
        cache.delete("onepipe:get_banks")
        response = client.get("/api/banks/")
        resp_data = response.json() if hasattr(response, 'json') else response.data
        
        print(f"  Response with root-level banks: {json.dumps(resp_data, indent=2)}")
        assert response.status_code == 200
        
        if isinstance(resp_data, list):
            assert len(resp_data) == 1
        else:
            assert "banks" in resp_data
            assert len(resp_data["banks"]) == 1
        
        print("  ✅ PASS: Handles root-level banks format")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing GET /api/banks/ Endpoint")
    print("=" * 60)
    
    try:
        test_banks_endpoint_public()
        test_banks_endpoint_caching()
        test_banks_endpoint_error_handling()
        test_banks_endpoint_response_formats()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
