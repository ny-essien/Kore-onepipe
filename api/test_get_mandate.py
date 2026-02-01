"""
Tests for GET /api/mandates/me/ endpoint.
"""
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from rest_framework import status
from .models import Profile, RulesEngine, Mandate
from datetime import date


class GetMandateTestCase(APITestCase):
    """Test GET /api/mandates/me/ endpoint"""

    def setUp(self):
        """Create test user and profile"""
        self.user = User.objects.create_user(
            username="testuser@example.com",
            email="testuser@example.com",
            password="testpass123"
        )
        self.profile, _ = Profile.objects.get_or_create(
            user=self.user,
            defaults={
                "first_name": "John",
                "surname": "Doe",
                "phone_number": "2348012345678",
                "is_completed": True,
            }
        )
        self.rules_engine = RulesEngine.objects.create(
            user=self.user,
            monthly_max_debit=50000,
            single_max_debit=10000,
            frequency="MONTHLY",
            amount_per_frequency=50000,
            failure_action="NOTIFY",
            start_date=date.today(),
        )

    def test_get_mandate_no_mandates_returns_404(self):
        """When user has no mandates, GET /api/mandates/me/ returns 404"""
        # Login
        self.client.force_authenticate(user=self.user)

        # GET /api/mandates/me/
        response = self.client.get("/api/mandates/me/")

        # Verify 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("No mandate found for this user.", response.data.get("error", ""))

    def test_get_mandate_with_single_mandate(self):
        """When user has one mandate, returns it with all fields"""
        # Create mandate
        mandate = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="ACTIVE",
            request_ref="test-request-ref-123",
            mandate_reference="mandate-ref-456",
            subscription_id=789,
            activation_url="https://example.com/activate",
            provider_response={"status": "Successful", "data": {"provider_response_code": "00"}},
        )

        # Login
        self.client.force_authenticate(user=self.user)

        # GET /api/mandates/me/
        response = self.client.get("/api/mandates/me/")

        # Verify 200 and fields
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["id"], mandate.id)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["mandate_reference"], "mandate-ref-456")
        self.assertEqual(data["subscription_id"], 789)
        self.assertEqual(data["request_ref"], "test-request-ref-123")
        self.assertEqual(data["activation_url"], "https://example.com/activate")
        self.assertIsNotNone(data["created_at"])
        self.assertIsNone(data["cancelled_at"])
        self.assertEqual(data["provider_response_code"], "00")

    def test_get_mandate_returns_latest_when_multiple(self):
        """When user has multiple mandates, returns the latest (by created_at)"""
        # Create first mandate
        mandate1 = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="FAILED",
            request_ref="test-request-ref-1",
        )

        # Create second mandate (newer)
        mandate2 = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="ACTIVE",
            request_ref="test-request-ref-2",
            mandate_reference="mandate-ref-latest",
        )

        # Login
        self.client.force_authenticate(user=self.user)

        # GET /api/mandates/me/
        response = self.client.get("/api/mandates/me/")

        # Verify returns mandate2 (latest)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], mandate2.id)
        self.assertEqual(response.data["status"], "ACTIVE")
        self.assertEqual(response.data["request_ref"], "test-request-ref-2")

    def test_get_mandate_with_cancelled_status(self):
        """Returns mandate with CANCELLED status and cancelled_at set"""
        from django.utils import timezone

        # Create cancelled mandate
        cancelled_time = timezone.now()
        mandate = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="CANCELLED",
            request_ref="test-request-ref-cancel",
            mandate_reference="mandate-ref-cancel",
            cancelled_at=cancelled_time,
            cancel_response={"status": "Successful", "data": {"provider_response_code": "00"}},
        )

        # Login
        self.client.force_authenticate(user=self.user)

        # GET /api/mandates/me/
        response = self.client.get("/api/mandates/me/")

        # Verify
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["status"], "CANCELLED")
        self.assertIsNotNone(data["cancelled_at"])
        # provider_response_code should be extracted from cancel_response
        self.assertEqual(data["provider_response_code"], "00")

    def test_get_mandate_no_auth_returns_401(self):
        """When not authenticated, GET /api/mandates/me/ returns 401"""
        response = self.client.get("/api/mandates/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_mandate_pending_status(self):
        """Returns mandate with PENDING status correctly"""
        mandate = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="PENDING",
            request_ref="test-request-ref-pending",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/mandates/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PENDING")

    def test_get_mandate_without_optional_fields(self):
        """Handles mandate missing optional fields (mandate_reference, subscription_id, etc.)"""
        # Create mandate with minimal fields
        mandate = Mandate.objects.create(
            user=self.user,
            rules_engine=self.rules_engine,
            status="ACTIVE",
            request_ref="test-request-ref-min",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/mandates/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["id"], mandate.id)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["mandate_reference"], "")  # blank
        self.assertIsNone(data["subscription_id"])  # null
        self.assertEqual(data["activation_url"], "")  # blank
        self.assertIsNone(data["provider_response_code"])  # no response data
