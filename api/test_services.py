"""
Tests for GET /api/services/ endpoint.
"""
from rest_framework.test import APITestCase
from rest_framework import status


class ServicesTestCase(APITestCase):
    """Test GET /api/services/ endpoint"""

    def test_get_services_no_auth_returns_200(self):
        """GET /api/services/ should return 200 without authentication"""
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_services_response_structure(self):
        """Response should have 'services' key with list of service objects"""
        response = self.client.get("/api/services/")
        data = response.data
        self.assertIn("services", data)
        self.assertIsInstance(data["services"], list)

    def test_get_services_returns_all_services(self):
        """Response should contain all 5 expected services"""
        response = self.client.get("/api/services/")
        services = response.data["services"]
        self.assertEqual(len(services), 5)

    def test_get_services_contains_correct_keys(self):
        """Each service should have 'key' and 'label' fields"""
        response = self.client.get("/api/services/")
        services = response.data["services"]
        for service in services:
            self.assertIn("key", service)
            self.assertIn("label", service)
            self.assertIsInstance(service["key"], str)
            self.assertIsInstance(service["label"], str)

    def test_get_services_keys_are_uppercase(self):
        """All service keys should be uppercase"""
        response = self.client.get("/api/services/")
        services = response.data["services"]
        for service in services:
            self.assertEqual(service["key"], service["key"].upper())

    def test_get_services_contains_specific_services(self):
        """Response should contain all expected services: SAVINGS, INVESTMENT, TAX, LOANS, BILLS"""
        response = self.client.get("/api/services/")
        services = response.data["services"]
        keys = [service["key"] for service in services]
        expected_keys = ["SAVINGS", "INVESTMENT", "TAX", "LOANS", "BILLS"]
        self.assertEqual(keys, expected_keys)

    def test_get_services_labels_are_human_readable(self):
        """Service labels should be human-readable"""
        response = self.client.get("/api/services/")
        services = response.data["services"]
        labels = [service["label"] for service in services]
        # All labels should be non-empty strings
        for label in labels:
            self.assertTrue(len(label) > 0)

    def test_get_services_with_auth_also_works(self):
        """GET /api/services/ should work with authentication token (still public)"""
        from django.contrib.auth.models import User
        user = User.objects.create_user(username="testuser", password="testpass")
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("services", response.data)

    def test_get_services_order_preserved(self):
        """Service order should be preserved across multiple requests"""
        response1 = self.client.get("/api/services/")
        response2 = self.client.get("/api/services/")
        
        keys1 = [s["key"] for s in response1.data["services"]]
        keys2 = [s["key"] for s in response2.data["services"]]
        
        self.assertEqual(keys1, keys2)
