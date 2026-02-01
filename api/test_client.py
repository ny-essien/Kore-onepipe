"""Small test client helpers for integration tests.

Provides `TestApiClient` which wraps Django's test client and exposes
convenience methods used across mandate-related tests.

Usage example:
    from django.test import Client
    from api.test_client import TestApiClient

    c = TestApiClient(Client())
    user = c.create_user('a@example.com')
    c.complete_profile(user)
    c.create_active_rules(user)
    resp = c.post_create_mandate(user)

This keeps test setup DRY.
"""
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .encryption import encrypt_value
from .models import RulesEngine
from decimal import Decimal
from datetime import date


class TestApiClient:
    def __init__(self, client):
        self.client = client

    def create_user(self, email="test@example.com", password="Pass1234!", first_name="Test"):
        user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name)
        return user

    def auth_client(self, user):
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def complete_profile(self, user, account_number="1234567890", bvn="12345678901", phone="2348012345678", bank_code="044"):
        profile = user.profile
        profile.first_name = getattr(user, "first_name", "") or ""
        profile.surname = "Test"
        profile.phone_number = phone
        profile.bank_code = bank_code
        profile.account_number_encrypted = encrypt_value(account_number)
        profile.bvn_encrypted = encrypt_value(bvn)
        profile.is_completed = True
        profile.save()
        return profile

    def create_active_rules(self, user, monthly="100000", single="50000"):
        rules = RulesEngine.objects.create(
            user=user,
            monthly_max_debit=Decimal(str(monthly)),
            single_max_debit=Decimal(str(single)),
            frequency='MONTHLY',
            amount_per_frequency=Decimal(str(monthly)),
            allocations=[{'bucket': 'ALL', 'percentage': 100}],
            failure_action='NOTIFY',
            start_date=date.today(),
            end_date=None,
            is_active=True,
        )
        return rules

    def post_create_mandate(self, user, data=None):
        # Ensure client is authenticated for user
        self.auth_client(user)
        payload = data or {}
        return self.client.post('/api/mandates/create/', data=payload, format='json')
