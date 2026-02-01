import os
import sys
import django
from datetime import date
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kore.settings")
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from api.models import RulesEngine

User = get_user_model()


def login_return_token(client, email, password):
    resp = client.post(
        "/api/auth/login/",
        {"email": email, "password": password},
        format="json",
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.content}"
    return resp.json()["tokens"]["access"]


def test_patch_no_active_rule():
    client = APIClient()

    # ensure clean
    User.objects.filter(username="patch_no_active@example.com").delete()

    user = User.objects.create_user(
        username="patch_no_active@example.com",
        email="patch_no_active@example.com",
        first_name="Patch NoActive",
        password="TestPass123!",
    )

    token = login_return_token(client, user.email, "TestPass123!")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.patch("/api/rules-engine/me/", {"monthly_max_debit": 10000}, format="json")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.content}"
    print("✓ PATCH returns 404 when no active rule exists")

    user.delete()


def test_patch_updates_allowed_fields():
    client = APIClient()

    # cleanup
    User.objects.filter(username="patch_update@example.com").delete()

    user = User.objects.create_user(
        username="patch_update@example.com",
        email="patch_update@example.com",
        first_name="Patch Update",
        password="TestPass123!",
    )

    # create active rule
    rule = RulesEngine.objects.create(
        user=user,
        monthly_max_debit=50000.00,
        single_max_debit=10000.00,
        frequency="MONTHLY",
        amount_per_frequency=50000.00,
        allocations=[{"bucket": "A", "percentage": 50}, {"bucket": "B", "percentage": 50}],
        failure_action="NOTIFY",
        start_date=date(2026, 2, 1),
        is_active=True,
    )

    token = login_return_token(client, user.email, "TestPass123!")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Partial update: change monthly_max_debit and allocations
    payload = {
        "monthly_max_debit": "60000.00",
        "allocations": [{"bucket": "A", "percentage": 30}, {"bucket": "B", "percentage": 70}],
    }

    response = client.patch("/api/rules-engine/me/", payload, format="json")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content}"

    data = response.json()
    assert data["monthly_max_debit"] == "60000.00"
    assert len(data["allocations"]) == 2
    assert float(data["allocations"][0]["percentage"]) + float(data["allocations"][1]["percentage"]) == 100

    # Verify DB updated
    rule.refresh_from_db()
    assert str(rule.monthly_max_debit) == "60000.00"

    print("✓ PATCH updates allowed fields successfully")

    rule.delete()
    user.delete()


def test_patch_rejects_invalid_allocations():
    client = APIClient()

    # cleanup
    User.objects.filter(username="patch_invalid_alloc@example.com").delete()

    user = User.objects.create_user(
        username="patch_invalid_alloc@example.com",
        email="patch_invalid_alloc@example.com",
        first_name="Patch Invalid",
        password="TestPass123!",
    )

    # create active rule
    rule = RulesEngine.objects.create(
        user=user,
        monthly_max_debit=50000.00,
        single_max_debit=10000.00,
        frequency="MONTHLY",
        amount_per_frequency=50000.00,
        allocations=[{"bucket": "A", "percentage": 50}, {"bucket": "B", "percentage": 50}],
        failure_action="NOTIFY",
        start_date=date(2026, 2, 1),
        is_active=True,
    )

    token = login_return_token(client, user.email, "TestPass123!")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    payload = {
        "allocations": [{"bucket": "A", "percentage": 60}, {"bucket": "B", "percentage": 30}],
    }

    response = client.patch("/api/rules-engine/me/", payload, format="json")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.content}"

    body = response.json()
    # Expect allocation total error somewhere in response
    msg = json.dumps(body)
    assert "Total percentage of allocations must equal 100" in msg or "Total percentage" in msg

    print("✓ PATCH rejects invalid allocations (sum != 100)")

    rule.delete()
    user.delete()


def test_disable_no_active_rule():
    client = APIClient()

    # cleanup
    User.objects.filter(username="disable_no_active@example.com").delete()

    user = User.objects.create_user(
        username="disable_no_active@example.com",
        email="disable_no_active@example.com",
        first_name="Disable NoActive",
        password="TestPass123!",
    )

    token = login_return_token(client, user.email, "TestPass123!")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post("/api/rules-engine/me/disable/", format="json")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.content}"

    print("✓ Disable returns 404 when no active rule exists")

    user.delete()


def test_disable_sets_inactive_and_get_returns_404():
    client = APIClient()

    # cleanup
    User.objects.filter(username="disable_active@example.com").delete()

    user = User.objects.create_user(
        username="disable_active@example.com",
        email="disable_active@example.com",
        first_name="Disable Active",
        password="TestPass123!",
    )

    rule = RulesEngine.objects.create(
        user=user,
        monthly_max_debit=70000.00,
        single_max_debit=15000.00,
        frequency="MONTHLY",
        amount_per_frequency=70000.00,
        allocations=[{"bucket": "A", "percentage": 100}],
        failure_action="NOTIFY",
        start_date=date(2026, 2, 1),
        is_active=True,
    )

    token = login_return_token(client, user.email, "TestPass123!")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post("/api/rules-engine/me/disable/", format="json")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content}"

    body = response.json()
    assert body.get("message") == "Rules engine disabled"
    assert body["rule"]["is_active"] == False

    # Now GET should return 404
    get_resp = client.get("/api/rules-engine/me/")
    assert get_resp.status_code == 404, f"Expected 404 after disable, got {get_resp.status_code}: {get_resp.content}"

    # Cleanup
    rule.delete()
    user.delete()

    print("✓ Disable sets is_active=False and GET returns 404 afterwards")


if __name__ == "__main__":
    try:
        print("[Test] PATCH no active rule...")
        test_patch_no_active_rule()

        print("[Test] PATCH updates allowed fields...")
        test_patch_updates_allowed_fields()

        print("[Test] PATCH rejects invalid allocations...")
        test_patch_rejects_invalid_allocations()

        print("[Test] Disable no active rule...")
        test_disable_no_active_rule()

        print("[Test] Disable sets inactive and GET returns 404...")
        test_disable_sets_inactive_and_get_returns_404()

        print("\n✓ All update/disable endpoint tests passed")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
