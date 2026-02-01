#!/usr/bin/env python
"""
Test script to verify RulesEngineSerializer functionality.
"""
import os
import sys
import django
from datetime import date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DJANGO_SETTINGS_MODULE'] = 'kore.settings'
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory
from api.models import RulesEngine
from api.serializers import RulesEngineSerializer


def test_rulesengine_serializer():
    print("\n" + "="*70)
    print("Testing RulesEngineSerializer")
    print("="*70)
    
    # Clean up
    User.objects.all().delete()
    RulesEngine.objects.all().delete()
    
    # Create test user
    user = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        first_name="Test",
        password="TestPass123!"
    )
    print(f"\n✓ Created test user: {user.email}")
    
    factory = APIRequestFactory()
    
    # Test 1: Valid rule creation
    print("\n[Test 1] Valid rule creation with all fields...")
    request = factory.post('/api/rules/')
    request.user = user
    
    valid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [
            {"bucket": "SAVINGS", "percentage": 50},
            {"bucket": "SPENDING", "percentage": 50}
        ],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=valid_data, context={"request": request})
    if serializer.is_valid():
        rule = serializer.save()
        print(f"✓ Created rule: {rule}")
        print(f"  User: {rule.user.email}")
        print(f"  Active: {rule.is_active}")
    else:
        print(f"✗ FAILED: {serializer.errors}")
    
    # Test 2: Negative numeric field validation
    print("\n[Test 2] Validate negative numeric fields are rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "-50000.00",  # Negative!
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "monthly_max_debit" in serializer.errors:
            print(f"✓ Correctly rejected negative value: {serializer.errors['monthly_max_debit'][0]}")
        else:
            print(f"✗ FAILED: Expected monthly_max_debit error")
    else:
        print(f"✗ FAILED: Should have rejected negative value")
    
    # Test 3: Invalid frequency
    print("\n[Test 3] Validate invalid frequency is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "INVALID_FREQ",  # Invalid!
        "amount_per_frequency": "50000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "frequency" in serializer.errors:
            print(f"✓ Correctly rejected invalid frequency: {serializer.errors['frequency'][0]}")
        else:
            print(f"✗ FAILED: Expected frequency error")
    else:
        print(f"✗ FAILED: Should have rejected invalid frequency")
    
    # Test 4: Empty allocations
    print("\n[Test 4] Validate empty allocations are rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [],  # Empty!
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "allocations" in serializer.errors:
            print(f"✓ Correctly rejected empty allocations: {serializer.errors['allocations'][0]}")
        else:
            print(f"✗ FAILED: Expected allocations error")
    else:
        print(f"✗ FAILED: Should have rejected empty allocations")
    
    # Test 5: Missing percentage in allocation
    print("\n[Test 5] Validate missing 'percentage' in allocation is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [
            {"bucket": "SAVINGS"}  # Missing percentage!
        ],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "allocations" in serializer.errors:
            print(f"✓ Correctly rejected missing percentage: {serializer.errors['allocations'][0]}")
        else:
            print(f"✗ FAILED: Expected allocations error")
    else:
        print(f"✗ FAILED: Should have rejected missing percentage")
    
    # Test 6: Invalid percentage value (not 1-100)
    print("\n[Test 6] Validate percentage outside 1-100 range is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [
            {"bucket": "SPENDING", "percentage": 150}  # Invalid!
        ],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "allocations" in serializer.errors:
            print(f"✓ Correctly rejected invalid percentage: {serializer.errors['allocations'][0]}")
        else:
            print(f"✗ FAILED: Expected allocations error")
    else:
        print(f"✗ FAILED: Should have rejected invalid percentage")
    
    # Test 7: Allocations don't sum to 100
    print("\n[Test 7] Validate allocations not summing to 100 are rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [
            {"bucket": "SAVINGS", "percentage": 50},
            {"bucket": "SPENDING", "percentage": 40}  # Total = 90, not 100!
        ],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "allocations" in serializer.errors:
            print(f"✓ Correctly rejected incorrect total: {serializer.errors['allocations'][0]}")
        else:
            print(f"✗ FAILED: Expected allocations error")
    else:
        print(f"✗ FAILED: Should have rejected incorrect total")
    
    # Test 8: Past start_date
    print("\n[Test 8] Validate past start_date is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(date.today() - timedelta(days=1)),  # Yesterday!
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "start_date" in serializer.errors:
            print(f"✓ Correctly rejected past date: {serializer.errors['start_date'][0]}")
        else:
            print(f"✗ FAILED: Expected start_date error")
    else:
        print(f"✗ FAILED: Should have rejected past date")
    
    # Test 9: end_date before start_date
    print("\n[Test 9] Validate end_date before start_date is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    start = date.today() + timedelta(days=10)
    end = date.today() + timedelta(days=5)  # Before start!
    
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(start),
        "end_date": str(end),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "end_date" in serializer.errors:
            print(f"✓ Correctly rejected end_date before start_date: {serializer.errors['end_date'][0]}")
        else:
            print(f"✗ FAILED: Expected end_date error")
    else:
        print(f"✗ FAILED: Should have rejected end_date before start_date")
    
    # Test 10: Deactivate existing active rule on create
    print("\n[Test 10] Verify existing active rule is deactivated on new rule creation...")
    
    # We should still have one active rule from Test 1
    active_rules_before = RulesEngine.objects.filter(user=user, is_active=True).count()
    print(f"  Active rules before: {active_rules_before}")
    
    # Create another rule
    request = factory.post('/api/rules/')
    request.user = user
    
    valid_data = {
        "monthly_max_debit": "30000.00",
        "single_max_debit": "5000.00",
        "frequency": "WEEKLY",
        "amount_per_frequency": "7000.00",
        "allocations": [
            {"bucket": "SAVINGS", "percentage": 60},
            {"bucket": "SPENDING", "percentage": 40}
        ],
        "failure_action": "SKIP",
        "start_date": str(date.today() + timedelta(days=1)),
    }
    
    serializer = RulesEngineSerializer(data=valid_data, context={"request": request})
    if serializer.is_valid():
        new_rule = serializer.save()
        
        active_rules_after = RulesEngine.objects.filter(user=user, is_active=True).count()
        print(f"  Active rules after: {active_rules_after}")
        
        if active_rules_after == 1:
            print(f"✓ Correctly deactivated old rule and kept only new one")
        else:
            print(f"✗ FAILED: Expected 1 active rule, got {active_rules_after}")
    else:
        print(f"✗ FAILED: {serializer.errors}")
    
    # Test 11: single_max_debit > monthly_max_debit
    print("\n[Test 11] Validate single_max_debit > monthly_max_debit is rejected...")
    request = factory.post('/api/rules/')
    request.user = user
    
    invalid_data = {
        "monthly_max_debit": "10000.00",
        "single_max_debit": "20000.00",  # Greater than monthly!
        "frequency": "MONTHLY",
        "amount_per_frequency": "10000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    serializer = RulesEngineSerializer(data=invalid_data, context={"request": request})
    if not serializer.is_valid():
        if "single_max_debit" in serializer.errors:
            print(f"✓ Correctly rejected invalid amounts: {serializer.errors['single_max_debit'][0]}")
        else:
            print(f"✗ FAILED: Expected single_max_debit error")
    else:
        print(f"✗ FAILED: Should have rejected single_max_debit > monthly_max_debit")
    
    # Summary
    print("\n" + "="*70)
    print("✓ All RulesEngineSerializer tests completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        test_rulesengine_serializer()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
