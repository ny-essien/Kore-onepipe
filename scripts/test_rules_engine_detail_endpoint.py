import os
import sys
import django
from datetime import date

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kore.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from api.models import RulesEngine

User = get_user_model()

def test_get_active_rule():
    """Test retrieving the active rule for authenticated user"""
    client = Client()
    
    # Clean up
    User.objects.filter(username="test@example.com").delete()
    
    # Create test user
    user = User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        first_name="Test User",
        password="testpass123"
    )
    
    # Create an active rule
    rule = RulesEngine.objects.create(
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
        start_date=date(2026, 2, 1),
        is_active=True
    )
    
    # Get JWT token
    response = client.post(
        "/api/auth/login/",
        {"email": "test@example.com", "password": "testpass123"},
        content_type="application/json"
    )
    token = response.json()["tokens"]["access"]
    
    # Test GET /api/rules-engine/me/
    response = client.get(
        "/api/rules-engine/me/",
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    data = response.json()
    
    assert data["id"] == rule.id
    assert data["monthly_max_debit"] == "50000.00"
    assert data["single_max_debit"] == "10000.00"
    assert data["frequency"] == "MONTHLY"
    assert data["is_active"] == True
    assert len(data["allocations"]) == 2
    
    print(f"✓ Successfully retrieved active rule: ID {rule.id}")
    
    # Cleanup
    rule.delete()
    user.delete()


def test_get_no_active_rule():
    """Test retrieving when no active rule exists"""
    client = Client()
    
    # Clean up
    User.objects.filter(username="test2@example.com").delete()
    
    # Create test user without rule
    user = User.objects.create_user(
        username="test2@example.com",
        email="test2@example.com",
        first_name="Test User 2",
        password="testpass123"
    )
    
    # Get JWT token
    response = client.post(
        "/api/auth/login/",
        {"email": "test2@example.com", "password": "testpass123"},
        content_type="application/json"
    )
    token = response.json()["tokens"]["access"]
    
    # Test GET /api/rules-engine/me/ - should return 404
    response = client.get(
        "/api/rules-engine/me/",
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.json()}"
    data = response.json()
    assert data["error"] == "No rules engine configured yet."
    
    print(f"✓ Correctly returned 404 when no active rule exists")
    
    # Cleanup
    user.delete()


def test_get_inactive_rule_returns_404():
    """Test that only active rules are returned"""
    client = Client()
    
    # Clean up
    User.objects.filter(username="test3@example.com").delete()
    
    # Create test user
    user = User.objects.create_user(
        username="test3@example.com",
        email="test3@example.com",
        first_name="Test User 3",
        password="testpass123"
    )
    
    # Create an inactive rule
    rule = RulesEngine.objects.create(
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
        start_date=date(2026, 2, 1),
        is_active=False
    )
    
    # Get JWT token
    response = client.post(
        "/api/auth/login/",
        {"email": "test3@example.com", "password": "testpass123"},
        content_type="application/json"
    )
    token = response.json()["tokens"]["access"]
    
    # Test GET /api/rules-engine/me/ - should return 404 since rule is inactive
    response = client.get(
        "/api/rules-engine/me/",
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.json()}"
    data = response.json()
    assert data["error"] == "No rules engine configured yet."
    
    print(f"✓ Correctly returned 404 when only inactive rules exist")
    
    # Cleanup
    rule.delete()
    user.delete()


def test_get_unauthenticated_returns_401():
    """Test that unauthenticated requests return 401"""
    client = Client()
    
    # Test GET /api/rules-engine/me/ without authentication
    response = client.get("/api/rules-engine/me/")
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.json()}"
    
    print(f"✓ Correctly returned 401 for unauthenticated request")


def test_user_only_sees_own_rule():
    """Test that users only see their own active rule"""
    client = Client()
    
    # Clean up
    User.objects.filter(username__in=["user1@example.com", "user2@example.com"]).delete()
    
    # Create two users
    user1 = User.objects.create_user(
        username="user1@example.com",
        email="user1@example.com",
        first_name="User 1",
        password="testpass123"
    )
    
    user2 = User.objects.create_user(
        username="user2@example.com",
        email="user2@example.com",
        first_name="User 2",
        password="testpass123"
    )
    
    # Create rules for both users
    rule1 = RulesEngine.objects.create(
        user=user1,
        monthly_max_debit=50000.00,
        single_max_debit=10000.00,
        frequency="MONTHLY",
        amount_per_frequency=50000.00,
        allocations=[
            {"bucket": "SAVINGS", "percentage": 50},
            {"bucket": "SPENDING", "percentage": 50}
        ],
        failure_action="NOTIFY",
        start_date=date(2026, 2, 1),
        is_active=True
    )
    
    rule2 = RulesEngine.objects.create(
        user=user2,
        monthly_max_debit=100000.00,
        single_max_debit=20000.00,
        frequency="DAILY",
        amount_per_frequency=5000.00,
        allocations=[
            {"bucket": "EMERGENCY", "percentage": 100}
        ],
        failure_action="RETRY",
        start_date=date(2026, 2, 1),
        is_active=True
    )
    
    # Get token for user1
    response = client.post(
        "/api/auth/login/",
        {"email": "user1@example.com", "password": "testpass123"},
        content_type="application/json"
    )
    token1 = response.json()["tokens"]["access"]
    
    # User1 should only see their own rule
    response = client.get(
        "/api/rules-engine/me/",
        HTTP_AUTHORIZATION=f"Bearer {token1}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rule1.id
    assert data["monthly_max_debit"] == "50000.00"
    assert data["single_max_debit"] == "10000.00"
    
    print(f"✓ User1 correctly sees only their own rule (ID {rule1.id})")
    
    # Get token for user2
    response = client.post(
        "/api/auth/login/",
        {"email": "user2@example.com", "password": "testpass123"},
        content_type="application/json"
    )
    token2 = response.json()["tokens"]["access"]
    
    # User2 should only see their own rule
    response = client.get(
        "/api/rules-engine/me/",
        HTTP_AUTHORIZATION=f"Bearer {token2}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rule2.id
    assert data["monthly_max_debit"] == "100000.00"
    assert data["single_max_debit"] == "20000.00"
    
    print(f"✓ User2 correctly sees only their own rule (ID {rule2.id})")
    
    # Cleanup
    rule1.delete()
    rule2.delete()
    user1.delete()
    user2.delete()


if __name__ == "__main__":
    try:
        print("[Test 1] Retrieve active rule for authenticated user...")
        test_get_active_rule()
        
        print("\n[Test 2] Get 404 when no active rule exists...")
        test_get_no_active_rule()
        
        print("\n[Test 3] Get 404 when only inactive rules exist...")
        test_get_inactive_rule_returns_404()
        
        print("\n[Test 4] Get 401 for unauthenticated request...")
        test_get_unauthenticated_returns_401()
        
        print("\n[Test 5] User only sees their own active rule...")
        test_user_only_sees_own_rule()
        
        print("\n✓ All RulesEngineDetailView tests completed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
