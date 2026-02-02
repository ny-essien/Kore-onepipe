"""Tests for the /api/banks/ endpoint."""
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.core.cache import cache


class BanksEndpointTestCase(APITestCase):
    """Test the GET /api/banks/ endpoint"""

    def setUp(self):
        """Clear cache before each test"""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def test_banks_endpoint_no_auth_required(self):
        """GET /api/banks/ should work without authentication"""
        response = self.client.get('/api/banks/', format='json')
        # Should return either 200 (with banks) or 502 (provider error)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_502_BAD_GATEWAY])

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_returns_list_of_banks(self, mock_transact):
        """GET /api/banks/ should return a list of banks with name and code"""
        # Mock the OnePipe response
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': [
                        {'bank_name': 'Access Bank', 'bank_code': '044'},
                        {'bank_name': 'GTBank', 'bank_code': '007'},
                        {'bank_name': 'Zenith Bank', 'bank_code': '057'},
                    ]
                }
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response should be a list
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        # Each bank should have name and code
        for bank in data:
            self.assertIn('name', bank)
            self.assertIn('code', bank)
            self.assertIsInstance(bank['name'], str)
            self.assertIsInstance(bank['code'], str)
            self.assertTrue(len(bank['code']) > 0)

    @patch('api.views.OnePipeClient.transact')
    def test_banks_returns_correct_data_structure(self, mock_transact):
        """Banks should have correct names and codes"""
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': [
                        {'bank_name': 'Access Bank', 'bank_code': '044'},
                        {'bank_name': 'GTBank', 'bank_code': '007'},
                    ]
                }
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 2)

        # Check specific banks
        self.assertEqual(data[0]['name'], 'Access Bank')
        self.assertEqual(data[0]['code'], '044')
        self.assertEqual(data[1]['name'], 'GTBank')
        self.assertEqual(data[1]['code'], '007')

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_handles_alternative_response_format(self, mock_transact):
        """Should handle alternative response structures (banks at top level)"""
        mock_transact.return_value = {
            'response': {
                'banks': [
                    {'bank_name': 'Access Bank', 'bank_code': '044'},
                    {'bank_name': 'GTBank', 'bank_code': '007'},
                ]
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_filters_banks_without_code(self, mock_transact):
        """Banks without code should be filtered out"""
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': [
                        {'bank_name': 'Access Bank', 'bank_code': '044'},
                        {'bank_name': 'Invalid Bank', 'bank_code': None},  # Should be filtered
                        {'bank_name': 'GTBank', 'bank_code': '007'},
                    ]
                }
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 2)  # Only 2 valid banks
        self.assertEqual(data[0]['code'], '044')
        self.assertEqual(data[1]['code'], '007')

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_caches_response(self, mock_transact):
        """Banks response should be cached for 1 hour"""
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': [
                        {'bank_name': 'Access Bank', 'bank_code': '044'},
                    ]
                }
            }
        }

        # First request - should call transact
        response1 = self.client.get('/api/banks/', format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_transact.call_count, 1)

        # Second request - should use cache
        response2 = self.client.get('/api/banks/', format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_transact.call_count, 1)  # Still 1, not 2

        # Responses should be identical
        self.assertEqual(response1.json(), response2.json())

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_returns_502_on_provider_error(self, mock_transact):
        """Should return 502 BAD_GATEWAY when provider returns no banks"""
        mock_transact.return_value = {
            'response': {
                'data': {}  # No banks in response
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

        data = response.json()
        self.assertIn('error', data)

    @patch('api.views.OnePipeClient.transact')
    def test_banks_endpoint_handles_empty_banks_list(self, mock_transact):
        """Should handle empty banks list gracefully"""
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': []  # Empty list
                }
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch('api.views.OnePipeClient.transact')
    def test_banks_uses_alternative_field_names(self, mock_transact):
        """Should handle alternative field names (name vs bank_name, code vs bank_code)"""
        mock_transact.return_value = {
            'response': {
                'data': {
                    'banks': [
                        {'name': 'Access Bank', 'code': '044'},  # Alternative names
                        {'bankFullName': 'GTBank', 'bankCode': '007'},  # Yet another format
                    ]
                }
            }
        }

        response = self.client.get('/api/banks/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'Access Bank')
        self.assertEqual(data[0]['code'], '044')
        self.assertEqual(data[1]['name'], 'GTBank')
        self.assertEqual(data[1]['code'], '007')
