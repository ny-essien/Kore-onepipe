#!/usr/bin/env python
"""
Test script to verify RulesEngine model functionality.
"""
import os
import sys
import django

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'kore.settings'
django.setup()

from django.contrib.auth.models import User
from api.models import RulesEngine
from django.core.exceptions import ValidationError

def test_rulesengine_model():
    print("\n" + "="*60)
    print("Testing RulesEngine Model")
    print("="*60)
    
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
    
    # Test 1: Create a basic rule
    print("\n[Test 1] Create a basic RulesEngine...")
    rule1 = RulesEngine.objects.create(
        user=user,
        monthly_max_debit=50000.00,
        single_max_debit=10000.00,
        frequency="MONTHLY",
        amount_per_frequency=50000.00,
        allocations=[
            {"bucket": "SAVINGS", "percentage": 50},
            {"bucket": "SPENDING", "percentage": 50}
        ],
        failure_action="NOTIFY",
        start_date=date.today(),
        is_active=True
    )
    print(f"✓ Created rule: {rule1}")
    print(f"  Monthly max: {rule1.monthly_max_debit}")
    print(f"  Single max: {rule1.single_max_debit}")
    print(f"  Frequency: {rule1.frequency}")
    print(f"  Allocations: {rule1.allocations}")
    
    # Test 2: Verify only one active rule per user
    print("\n[Test 2] Verify only one active rule per user...")
    try:
        rule2 = RulesEngine(
            user=user,
            monthly_max_debit=30000.00,
            single_max_debit=5000.00,
            frequency="WEEKLY",
            amount_per_frequency=7000.00,
            failure_action="SKIP",
            start_date=date.today(),
            is_active=True
        )
        rule2.save()
        print("✗ FAILED: Should have prevented second active rule!")
    except ValidationError as e:
        print(f"✓ Correctly prevented duplicate active rule: {e.message}")
    
    # Test 3: Allow multiple inactive rules
    print("\n[Test 3] Allow inactive rules for same user...")
    rule3 = RulesEngine.objects.create(
        user=user,
        monthly_max_debit=20000.00,
        single_max_debit=3000.00,
        frequency="DAILY",
        amount_per_frequency=2000.00,
        failure_action="RETRY",
        start_date=date.today() + timedelta(days=30),
        is_active=False
    )
    print(f"✓ Created inactive rule: {rule3}")
    
    # Test 4: Verify date validation
    print("\n[Test 4] Verify date validation...")
    try:
        invalid_rule = RulesEngine(
            user=user,
            monthly_max_debit=25000.00,
            single_max_debit=5000.00,
            frequency="MONTHLY",
            amount_per_frequency=25000.00,
            failure_action="NOTIFY",
            start_date=date.today(),
            end_date=date.today() - timedelta(days=1),  # End date before start date
            is_active=False
        )
        invalid_rule.save()
        print("✗ FAILED: Should have rejected end_date before start_date!")
    except ValidationError as e:
        print(f"✓ Correctly rejected invalid date range: {e.message}")
    
    # Test 5: Verify rule counts
    print("\n[Test 5] Verify rule counts...")
    user_rules = RulesEngine.objects.filter(user=user)
    active_rules = user_rules.filter(is_active=True)
    print(f"✓ Total rules for user: {user_rules.count()}")
    print(f"✓ Active rules for user: {active_rules.count()}")
    assert user_rules.count() == 2, "Expected 2 total rules"
    assert active_rules.count() == 1, "Expected 1 active rule"
    
    # Test 6: Verify frequency choices
    print("\n[Test 6] Verify frequency choices...")
    frequencies = dict(RulesEngine.FREQUENCY_CHOICES)
    print(f"✓ Available frequencies: {list(frequencies.keys())}")
    
    # Test 7: Verify failure action choices
    print("\n[Test 7] Verify failure action choices...")
    actions = dict(RulesEngine.FAILURE_ACTION_CHOICES)
    print(f"✓ Available failure actions: {list(actions.keys())}")
    
    # Summary
    print("\n" + "="*60)
    print("✓ All RulesEngine tests passed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        test_rulesengine_model()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
