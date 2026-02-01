from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date

from .models import Mandate, RulesEngine
from .test_client import TestApiClient
from .encryption import encrypt_value


class CancelMandateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cuser', email='cuser@example.com', password='Pass1234!', first_name='C')
        self.tclient = TestApiClient(self.client)

    def test_no_active_mandate_returns_404(self):
        self.tclient.auth_client(self.user)
        resp = self.client.post('/api/mandates/cancel/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)  # serializer returns 400 for no active mandate

    def test_missing_payment_id_returns_400(self):
        # create active mandate without payment_id
        self.tclient.complete_profile(self.user)
        self.tclient.create_active_rules(self.user)
        m = Mandate.objects.create(user=self.user, status='ACTIVE', request_ref='r1')
        self.tclient.auth_client(self.user)
        resp = self.client.post('/api/mandates/cancel/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.OnePipeClient.transact')
    def test_successful_cancellation_sets_cancelled(self, mock_transact):
        # Prepare active mandate with payment_id
        self.tclient.complete_profile(self.user)
        self.tclient.create_active_rules(self.user)
        m = Mandate.objects.create(user=self.user, status='ACTIVE', request_ref='r2', payment_id='pay-1')

        mock_transact.return_value = {'request_ref': 'c-1', 'response': {'status': 'Successful', 'data': {}}}

        self.tclient.auth_client(self.user)
        resp = self.client.post('/api/mandates/cancel/', data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        m.refresh_from_db()
        self.assertEqual(m.status, 'CANCELLED')
