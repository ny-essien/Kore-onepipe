#!/usr/bin/env python
"""
Test script to verify RulesEngineCreateView API endpoint.
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
from rest_framework.test import APIClient
from api.models import RulesEngine
import json


def test_rules_engine_endpoint():
    print("\n" + "="*70)
    print("Testing RulesEngineCreateView API Endpoint")
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
    
    client = APIClient()
    
    # Test 1: Unauthenticated request should fail
    print("\n[Test 1] Unauthenticated request should return 401...")
    response = client.post('/api/rules-engine/', {}, format='json')
    
    if response.status_code == 401:
        print(f"✓ Correctly rejected unauthenticated request: {response.status_code}")
    else:
        print(f"✗ FAILED: Expected 401, got {response.status_code}")
    
    # Authenticate the client
    client.force_authenticate(user=user)
    print(f"\n✓ Authenticated as: {user.email}")
    
    # Test 2: Valid rule creation
    print("\n[Test 2] Valid rule creation...")
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
    
    response = client.post('/api/rules-engine/', valid_data, format='json')
    
    if response.status_code == 201:
        data = response.json()
        print(f"✓ Successfully created rule: Status {response.status_code}")
        print(f"  Message: {data.get('message')}")
        print(f"  Ready for mandate: {data.get('ready_for_mandate')}")
        
        if data.get('ready_for_mandate') == True:
            print(f"✓ Response includes 'ready_for_mandate': true")
        else:
            print(f"✗ FAILED: 'ready_for_mandate' not true")
        
        if 'rule' in data:
            rule_data = data['rule']
            print(f"  Rule ID: {rule_data.get('id')}")
            print(f"  User attached: {rule_data.get('user')}")
            print(f"  Is active: {rule_data.get('is_active')}")
    else:
        print(f"✗ FAILED: Expected 201, got {response.status_code}")
        print(f"  Response: {response.json()}")
    
    # Test 3: Invalid data should return 400
    print("\n[Test 3] Invalid data returns 400...")
    invalid_data = {
        "monthly_max_debit": "-50000.00",  # Negative!
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    response = client.post('/api/rules-engine/', invalid_data, format='json')
    
    if response.status_code == 400:
        errors = response.json()
        print(f"✓ Correctly rejected invalid data: Status {response.status_code}")
        if 'monthly_max_debit' in errors:
            print(f"  Error: {errors['monthly_max_debit']}")
    else:
        print(f"✗ FAILED: Expected 400, got {response.status_code}")
    
    # Test 4: Invalid allocation percentages
    print("\n[Test 4] Invalid allocation percentages return 400...")
    invalid_data = {
        "monthly_max_debit": "50000.00",
        "single_max_debit": "10000.00",
        "frequency": "MONTHLY",
        "amount_per_frequency": "50000.00",
        "allocations": [
            {"bucket": "SAVINGS", "percentage": 50},
            {"bucket": "SPENDING", "percentage": 40}  # Total = 90, not 100
        ],
        "failure_action": "NOTIFY",
        "start_date": str(date.today()),
    }
    
    response = client.post('/api/rules-engine/', invalid_data, format='json')
    
    if response.status_code == 400:
        errors = response.json()
        print(f"✓ Correctly rejected invalid percentages: Status {response.status_code}")
        if 'allocations' in errors:
            print(f"  Error: {errors['allocations']}")
    else:
        print(f"✗ FAILED: Expected 400, got {response.status_code}")
    
    # Test 5: Create another rule - should deactivate previous one
    print("\n[Test 5] Second rule creation deactivates first rule...")
    
    new_data = {
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
    
    response = client.post('/api/rules-engine/', new_data, format='json')
    
    if response.status_code == 201:
        print(f"✓ Successfully created second rule: Status {response.status_code}")
        
        # Check only one is active
        active_count = RulesEngine.objects.filter(user=user, is_active=True).count()
        total_count = RulesEngine.objects.filter(user=user).count()
        
        print(f"  Total rules: {total_count}")
        print(f"  Active rules: {active_count}")
        
        if active_count == 1 and total_count == 2:
            print(f"✓ First rule was deactivated, second is now active")
        else:
            print(f"✗ FAILED: Expected 1 active of 2 total, got {active_count} active of {total_count} total")
    else:
        print(f"✗ FAILED: Expected 201, got {response.status_code}")
        print(f"  Response: {response.json()}")
    
    # Test 6: Verify rules are attached to correct user
    print("\n[Test 6] Verify rules are attached to correct user...")
    user_rules = RulesEngine.objects.filter(user=user)
    
    if user_rules.count() == 2:
        print(f"✓ User has 2 rules")
        for rule in user_rules:
            print(f"  - Rule {rule.id}: Active={rule.is_active}, Frequency={rule.frequency}")
    else:
        print(f"✗ FAILED: Expected 2 rules, got {user_rules.count()}")
    
    # Test 7: Verify response structure
    print("\n[Test 7] Verify response structure...")
    response = client.post('/api/rules-engine/', {
        "monthly_max_debit": "25000.00",
        "single_max_debit": "5000.00",
        "frequency": "DAILY",
        "amount_per_frequency": "2000.00",
        "allocations": [{"bucket": "SPENDING", "percentage": 100}],
        "failure_action": "RETRY",
        "start_date": str(date.today() + timedelta(days=2)),
    }, format='json')
    
    if response.status_code == 201:
        data = response.json()
        required_fields = ["message", "rule", "ready_for_mandate"]
        
        missing = [f for f in required_fields if f not in data]
        if not missing:
            print(f"✓ Response includes all required fields: {required_fields}")
            
            rule_fields = data['rule']
            if 'id' in rule_fields and 'monthly_max_debit' in rule_fields:
                print(f"✓ Rule data includes necessary fields")
        else:
            print(f"✗ FAILED: Missing fields: {missing}")
    else:
        print(f"✗ FAILED: Expected 201, got {response.status_code}")
    
    # Summary
    print("\n" + "="*70)
    print("✓ All RulesEngineCreateView tests completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        test_rules_engine_endpoint()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
