from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from .models import Profile, RulesEngine, Mandate
from .encryption import encrypt_value
from .test_client import TestApiClient


class MandateEndpointTests(APITestCase):
    def setUp(self):
        self.email = "mandateuser@example.com"
        self.password = "Pass1234!"
        self.user = User.objects.create_user(username=self.email, email=self.email, password=self.password, first_name="Test")
        self.profile = self.user.profile
        # default profile.is_completed is False
        # Test helper client
        self.tclient = TestApiClient(self.client)

    def create_active_rules(self):
        return self.tclient.create_active_rules(self.user)

    def ensure_profile_complete_with_bank(self):
        return self.tclient.complete_profile(self.user)

    def test_profile_not_completed_returns_400(self):
        self.tclient.auth_client(self.user)
        resp = self.tclient.post_create_mandate(self.user, data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_active_rules_engine_returns_400(self):
        # Make profile completed but no rules
        self.ensure_profile_complete_with_bank()
        self.tclient.auth_client(self.user)
        resp = self.tclient.post_create_mandate(self.user, data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.OnePipeClient.transact')
    def test_onepipe_success_creates_mandate_and_returns_activation(self, mock_transact):
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()
        self.tclient.auth_client(self.user)

        mock_transact.return_value = {
            'request_ref': 'req-123',
            'response': {'status': 'Successful', 'data': {'activation_url': 'https://activate', 'transaction_ref': 'tx-1'}}
        }

        resp = self.tclient.post_create_mandate(self.user, data={})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('activation_url', resp.data)
        self.assertEqual(resp.data['activation_url'], 'https://activate')

        # Mandate saved
        m = Mandate.objects.get(request_ref='req-123')
        self.assertEqual(m.status, 'PENDING')
        self.assertEqual(m.activation_url, 'https://activate')

    @patch('api.views.OnePipeClient.transact')
    def test_onepipe_failure_saves_failed_mandate_and_returns_400(self, mock_transact):
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()
        self.tclient.auth_client(self.user)

        mock_transact.return_value = {
            'request_ref': 'req-456',
            'response': {'status': 'Failed', 'message': 'provider error'}
        }

        resp = self.tclient.post_create_mandate(self.user, data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        m = Mandate.objects.get(request_ref='req-456')
        self.assertEqual(m.status, 'FAILED')

    def test_get_mandates_me_no_mandates_returns_404(self):
        self.tclient.auth_client(self.user)
        resp = self.client.get('/api/mandates/me/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_mandates_me_returns_latest_mandate(self):
        # Prepare two mandates, ensure latest is returned
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()

        m1 = Mandate.objects.create(
            user=self.user,
            rules_engine=RulesEngine.get_active_for_user(self.user),
            status='PENDING',
            request_ref='r-old',
            activation_url='https://old',
            provider_response={'status': 'Successful'},
        )

        m2 = Mandate.objects.create(
            user=self.user,
            rules_engine=RulesEngine.get_active_for_user(self.user),
            status='PENDING',
            request_ref='r-new',
            activation_url='https://new',
            provider_response={'status': 'Successful'},
        )

        self.tclient.auth_client(self.user)
        resp = self.client.get('/api/mandates/me/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('request_ref'), 'r-new')
        self.assertEqual(resp.data.get('activation_url'), 'https://new')
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from .models import Profile, RulesEngine, Mandate
from .encryption import encrypt_value


class MandateEndpointTests(APITestCase):
    def setUp(self):
        self.email = "mandateuser@example.com"
        self.password = "Pass1234!"
        self.user = User.objects.create_user(username=self.email, email=self.email, password=self.password, first_name="Test")
        self.profile = self.user.profile
        # default profile.is_completed is False

        # Helper to auth client
    def auth_client(self):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def create_active_rules(self):
        rules = RulesEngine.objects.create(
            user=self.user,
            monthly_max_debit=Decimal('100000'),
            single_max_debit=Decimal('50000'),
            frequency='MONTHLY',
            amount_per_frequency=Decimal('100000'),
            allocations=[{'bucket': 'ALL', 'percentage': 100}],
            failure_action='NOTIFY',
            start_date=date.today(),
            end_date=None,
            is_active=True,
        )
        return rules

    def ensure_profile_complete_with_bank(self):
        # Fill required fields and encrypt account & bvn
        self.profile.first_name = "John"
        self.profile.surname = "Doe"
        self.profile.phone_number = "2348012345678"
        self.profile.bank_code = "044"
        self.profile.account_number_encrypted = encrypt_value("1234567890")
        self.profile.bvn_encrypted = encrypt_value("12345678901")
        self.profile.is_completed = True
        self.profile.save()

    def test_profile_not_completed_returns_400(self):
        self.auth_client()
        resp = self.client.post('/api/mandates/create/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_active_rules_engine_returns_400(self):
        # Make profile completed but no rules
        self.ensure_profile_complete_with_bank()
        self.auth_client()
        resp = self.client.post('/api/mandates/create/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.OnePipeClient.transact')
    def test_onepipe_success_creates_mandate_and_returns_activation(self, mock_transact):
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()
        self.auth_client()

        mock_transact.return_value = {
            'request_ref': 'req-123',
            'response': {'status': 'Successful', 'data': {'activation_url': 'https://activate', 'transaction_ref': 'tx-1'}}
        }

        resp = self.client.post('/api/mandates/create/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('activation_url', resp.data)
        self.assertEqual(resp.data['activation_url'], 'https://activate')

        # Mandate saved
        m = Mandate.objects.get(request_ref='req-123')
        self.assertEqual(m.status, 'PENDING')
        self.assertEqual(m.activation_url, 'https://activate')

    @patch('api.views.OnePipeClient.transact')
    def test_onepipe_failure_saves_failed_mandate_and_returns_400(self, mock_transact):
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()
        self.auth_client()

        mock_transact.return_value = {
            'request_ref': 'req-456',
            'response': {'status': 'Failed', 'message': 'provider error'}
        }

        resp = self.client.post('/api/mandates/create/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        m = Mandate.objects.get(request_ref='req-456')
        self.assertEqual(m.status, 'FAILED')

    def test_get_mandates_me_no_mandates_returns_404(self):
        self.auth_client()
        resp = self.client.get('/api/mandates/me/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_mandates_me_returns_latest_mandate(self):
        # Prepare two mandates, ensure latest is returned
        self.ensure_profile_complete_with_bank()
        self.create_active_rules()

        m1 = Mandate.objects.create(
            user=self.user,
            rules_engine=RulesEngine.get_active_for_user(self.user),
            status='PENDING',
            request_ref='r-old',
            activation_url='https://old',
            provider_response={'status': 'Successful'},
        )

        m2 = Mandate.objects.create(
            user=self.user,
            rules_engine=RulesEngine.get_active_for_user(self.user),
            status='PENDING',
            request_ref='r-new',
            activation_url='https://new',
            provider_response={'status': 'Successful'},
        )

        self.auth_client()
        resp = self.client.get('/api/mandates/me/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('request_ref'), 'r-new')
        self.assertEqual(resp.data.get('activation_url'), 'https://new')
