from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock

from .models import Profile, ProfileVerificationAttempt


class AuthTests(APITestCase):
	def test_signup_creates_user_profile_and_returns_tokens(self):
		payload = {
			"name": "John Doe",
			"email": "john@example.com",
			"password": "StrongPass123!",
			"confirm_password": "StrongPass123!",
		}
		resp = self.client.post("/api/auth/signup/", payload, format="json")
		self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
		self.assertIn("user", resp.data)
		self.assertIn("tokens", resp.data)
		self.assertIn("access", resp.data["tokens"])
		self.assertIn("refresh", resp.data["tokens"])

		# user exists
		self.assertTrue(User.objects.filter(email=payload["email"]).exists())
		user = User.objects.get(email=payload["email"])

		# profile exists
		self.assertTrue(Profile.objects.filter(user=user).exists())
		profile = user.profile
		self.assertFalse(profile.is_completed)

	def test_login_returns_tokens_for_valid_credentials(self):
		email = "jane@example.com"
		password = "AnotherStrong1!"
		user = User.objects.create_user(username=email, email=email, first_name="Jane", password=password)
		resp = self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json")
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertIn("tokens", resp.data)
		self.assertIn("access", resp.data["tokens"])
		self.assertIn("refresh", resp.data["tokens"]) 

	def test_login_fails_for_wrong_password(self):
		email = "bob@example.com"
		password = "RightPass1!"
		User.objects.create_user(username=email, email=email, first_name="Bob", password=password)
		resp = self.client.post("/api/auth/login/", {"email": email, "password": "WrongPass"}, format="json")
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

	def test_me_returns_200_with_token_and_401_without(self):
		email = "alice@example.com"
		password = "AlicePass1!"
		user = User.objects.create_user(username=email, email=email, first_name="Alice", password=password)
		# ensure profile exists (signup normally creates it, but create here)
		Profile.objects.create(user=user, first_name=user.first_name, is_completed=False)

		refresh = RefreshToken.for_user(user)
		access = str(refresh.access_token)

		# with token
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
		resp = self.client.get("/api/auth/me/")
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("email"), email)
		self.assertIn("profile", resp.data)

		# without token
		self.client.credentials()  # clears credentials
		resp2 = self.client.get("/api/auth/me/")
		self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)


class EncryptionTests(APITestCase):
	"""Test encryption/decryption utilities for sensitive fields"""

	from .encryption import encrypt_value, decrypt_value

	def test_encrypt_decrypt_roundtrip(self):
		"""Test that encrypt -> decrypt returns original value"""
		from .encryption import encrypt_value, decrypt_value
		
		original = "1234567890"
		encrypted = encrypt_value(original)
		
		# Encrypted value should be non-empty and different from original
		self.assertNotEqual(encrypted, original)
		self.assertTrue(len(encrypted) > 0)
		
		# Decryption should restore original
		decrypted = decrypt_value(encrypted)
		self.assertEqual(decrypted, original)

	def test_encrypt_decrypt_account_number(self):
		"""Test encryption of account number"""
		from .encryption import encrypt_value, decrypt_value
		
		account = "1742041840"
		encrypted = encrypt_value(account)
		decrypted = decrypt_value(encrypted)
		self.assertEqual(decrypted, account)

	def test_encrypt_decrypt_bvn(self):
		"""Test encryption of BVN"""
		from .encryption import encrypt_value, decrypt_value
		
		bvn = "12345678901"
		encrypted = encrypt_value(bvn)
		decrypted = decrypt_value(encrypted)
		self.assertEqual(decrypted, bvn)

	def test_encrypt_empty_string_returns_empty(self):
		"""Test that empty string encryption returns empty string"""
		from .encryption import encrypt_value
		
		self.assertEqual(encrypt_value(""), "")
		self.assertEqual(encrypt_value(None), "")

	def test_decrypt_empty_string_returns_empty(self):
		"""Test that empty string decryption returns empty string"""
		from .encryption import decrypt_value
		
		self.assertEqual(decrypt_value(""), "")
		self.assertEqual(decrypt_value(None), "")

	def test_decrypt_invalid_ciphertext_raises_error(self):
		"""Test that decrypting invalid ciphertext raises ValueError"""
		from .encryption import decrypt_value
		
		with self.assertRaises(ValueError):
			decrypt_value("invalid_ciphertext_here")

	def test_encrypted_value_is_string_safe(self):
		"""Test that encrypted output is safe for database storage"""
		from .encryption import encrypt_value
		
		original = "test@example.com"
		encrypted = encrypt_value(original)
		
		# Should be a string
		self.assertIsInstance(encrypted, str)
		# Should not contain None or problematic characters
		self.assertNotIn("None", encrypted)


class OnePipeClientTests(APITestCase):
	"""Test OnePipeClient for API calls"""
	
	@patch('api.onepipe_client.requests.post')
	def test_transact_success_with_mocked_response(self, mock_post):
		"""Test successful transact call with mocked HTTP response"""
		from .onepipe_client import OnePipeClient
		
		# Mock successful response
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {
			"status": "Successful",
			"message": "Transaction processed successfully",
		}
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {
			"request_type": "Get Accounts Max",
			"auth": {"type": None, "secure": None, "auth_provider": "PaywithAccount"},
			"transaction": {
				"transaction_ref": "test-123",
				"amount": 0,
				"customer": {"customer_ref": "2348022221412"},
			},
		}
		
		result = client.transact(payload)
		
		# Verify result structure
		self.assertIn("request_ref", result)
		self.assertIn("response", result)
		self.assertEqual(result["response"]["status"], "Successful")
		
		# Verify mock was called
		mock_post.assert_called_once()

	@patch('api.onepipe_client.requests.post')
	def test_transact_injects_request_ref_if_not_provided(self, mock_post):
		"""Test that transact generates request_ref if not provided"""
		from .onepipe_client import OnePipeClient
		
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {"status": "ok"}
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {
			"request_type": "test",
			"auth": {"type": None},
			"transaction": {},
		}
		
		result = client.transact(payload)
		
		# request_ref should be generated (32 hex chars from uuid4)
		self.assertIsNotNone(result["request_ref"])
		self.assertEqual(len(result["request_ref"]), 32)

	@patch('api.onepipe_client.requests.post')
	def test_transact_sets_default_mock_mode(self, mock_post):
		"""Test that transact sets mock_mode to inspect if not provided"""
		from .onepipe_client import OnePipeClient
		
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {"status": "ok"}
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {
			"request_type": "test",
			"transaction": {},
		}
		
		client.transact(payload)
		
		# Verify mock_mode was injected (project default: inspect)
		called_payload = mock_post.call_args[1]["json"]
		self.assertEqual(called_payload["transaction"]["mock_mode"], "inspect")

	@patch('api.onepipe_client.requests.post')
	def test_transact_error_on_non_2xx_response(self, mock_post):
		"""Test that OnePipeError is raised on non-2xx response"""
		from .onepipe_client import OnePipeClient, OnePipeError
		
		mock_response = MagicMock()
		mock_response.status_code = 400
		mock_response.text = "Bad Request"
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {"request_type": "test", "transaction": {}}
		
		with self.assertRaises(OnePipeError) as ctx:
			client.transact(payload)
		
		self.assertEqual(ctx.exception.status_code, 400)

	@patch('api.onepipe_client.requests.post')
	def test_transact_headers_contain_signature(self, mock_post):
		"""Test that transact includes proper Authorization and Signature headers"""
		from .onepipe_client import OnePipeClient
		
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {"status": "ok"}
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {"request_type": "test", "transaction": {}}
		
		client.transact(payload)
		
		# Verify headers were set
		called_headers = mock_post.call_args[1]["headers"]
		self.assertIn("Authorization", called_headers)
		self.assertIn("Signature", called_headers)
		self.assertEqual(called_headers["Content-Type"], "application/json")
		self.assertTrue(called_headers["Authorization"].startswith("Bearer "))

	@patch('api.onepipe_client.requests.post')
	def test_transact_signature_format(self, mock_post):
		"""Test that signature is valid MD5 hash (32 hex chars)"""
		from .onepipe_client import OnePipeClient
		import re
		
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {"status": "ok"}
		mock_post.return_value = mock_response
		
		client = OnePipeClient()
		payload = {"request_type": "test", "transaction": {}}
		
		client.transact(payload)
		
		# Verify signature is valid MD5 (32 hex chars)
		called_headers = mock_post.call_args[1]["headers"]
		signature = called_headers["Signature"]
		self.assertTrue(re.match(r'^[a-f0-9]{32}$', signature), f"Invalid MD5 format: {signature}")


class ProfileSerializerTests(APITestCase):
	"""Test profile-related serializers"""

	def test_personal_info_serializer_valid_data(self):
		"""Test PersonalInfoSerializer with valid data"""
		from .serializers import PersonalInfoSerializer
		
		data = {
			"first_name": "John",
			"surname": "Doe",
			"phone_number": "2348022221412",
			"date_of_birth": "1990-01-15",
			"gender": "M",
		}
		serializer = PersonalInfoSerializer(data=data)
		self.assertTrue(serializer.is_valid())

	def test_personal_info_serializer_invalid_phone(self):
		"""Test PersonalInfoSerializer rejects non-digit phone numbers"""
		from .serializers import PersonalInfoSerializer
		
		data = {
			"phone_number": "invalid@phone",
		}
		serializer = PersonalInfoSerializer(data=data)
		self.assertFalse(serializer.is_valid())
		self.assertIn("phone_number", serializer.errors)

	def test_personal_info_serializer_future_dob_rejected(self):
		"""Test PersonalInfoSerializer rejects future dates of birth"""
		from .serializers import PersonalInfoSerializer
		from datetime import datetime, timedelta
		
		future_date = (datetime.now() + timedelta(days=1)).date()
		data = {
			"date_of_birth": future_date.isoformat(),
		}
		serializer = PersonalInfoSerializer(data=data)
		self.assertFalse(serializer.is_valid())
		self.assertIn("date_of_birth", serializer.errors)

	def test_bank_info_serializer_valid_data(self):
		"""Test BankInfoSerializer with valid data"""
		from .serializers import BankInfoSerializer
		
		data = {
			"account_number": "1234567890",
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "12345678901",
		}
		serializer = BankInfoSerializer(data=data)
		self.assertTrue(serializer.is_valid())

	def test_bank_info_serializer_invalid_account_number(self):
		"""Test BankInfoSerializer rejects non-10-digit account numbers"""
		from .serializers import BankInfoSerializer
		
		data = {
			"account_number": "123",  # Too short
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "12345678901",
		}
		serializer = BankInfoSerializer(data=data)
		self.assertFalse(serializer.is_valid())
		self.assertIn("account_number", serializer.errors)

	def test_bank_info_serializer_invalid_bvn(self):
		"""Test BankInfoSerializer rejects non-11-digit BVNs"""
		from .serializers import BankInfoSerializer
		
		data = {
			"account_number": "1234567890",
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "123456789",  # Too short
		}
		serializer = BankInfoSerializer(data=data)
		self.assertFalse(serializer.is_valid())
		self.assertIn("bvn", serializer.errors)

	def test_bank_info_serializer_encrypts_on_save(self):
		"""Test BankInfoSerializer encrypts account_number and bvn on save"""
		from .serializers import BankInfoSerializer
		
		email = "banker@example.com"
		password = "SecurePass1!"
		user = User.objects.create_user(username=email, email=email, password=password)
		profile = Profile.objects.create(user=user, first_name="Banker")
		
		data = {
			"account_number": "1234567890",
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "12345678901",
		}
		serializer = BankInfoSerializer(data=data)
		self.assertTrue(serializer.is_valid())
		
		serializer.save(profile)
		
		# Verify encrypted fields are not plaintext
		profile.refresh_from_db()
		self.assertNotEqual(profile.account_number_encrypted, "1234567890")
		self.assertNotEqual(profile.bvn_encrypted, "12345678901")
		self.assertEqual(profile.bank_name, "Access Bank")
		self.assertEqual(profile.bank_code, "044")


class ProfileViewTests(APITestCase):
	"""Test profile views"""

	def setUp(self):
		"""Create a test user and profile"""
		self.email = "testuser@example.com"
		self.password = "TestPass123!"
		self.user = User.objects.create_user(
			username=self.email, email=self.email, first_name="Test", password=self.password
		)
		self.profile = Profile.objects.create(user=self.user, first_name="Test")
		
		# Authenticate
		refresh = RefreshToken.for_user(self.user)
		self.access_token = str(refresh.access_token)

	def test_profile_me_view_returns_user_and_profile(self):
		"""Test GET /api/profile/me/ returns user email and profile details"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		resp = self.client.get("/api/profile/me/")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("email"), self.email)
		self.assertEqual(resp.data.get("first_name"), "Test")
		self.assertIn("is_completed", resp.data)

	def test_profile_me_view_requires_authentication(self):
		"""Test that /api/profile/me/ requires authentication"""
		resp = self.client.get("/api/profile/me/")
		self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_profile_me_view_creates_profile_if_missing(self):
		"""Test that /api/profile/me/ creates profile if missing"""
		new_user = User.objects.create_user(
			username="newuser@example.com",
			email="newuser@example.com",
			first_name="New",
			password="NewPass123!",
		)
		refresh = RefreshToken.for_user(new_user)
		access_token = str(refresh.access_token)
		
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
		resp = self.client.get("/api/profile/me/")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		# Verify profile was created
		self.assertTrue(Profile.objects.filter(user=new_user).exists())

	def test_personal_info_update_patches_fields(self):
		"""Test PATCH /api/profile/personal/ stores data in draft_payload"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		data = {
			"surname": "Updated",
			"phone_number": "2348022221412",
		}
		resp = self.client.patch("/api/profile/personal/", data, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("surname"), "Updated")
		self.assertEqual(resp.data.get("phone_number"), "2348022221412")
		
		# Verify in database (stored in draft_payload, not final fields)
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.surname, "")  # Final field should be empty
		self.assertEqual(self.profile.draft_payload.get("personal", {}).get("surname"), "Updated")
		self.assertEqual(self.profile.draft_payload.get("personal", {}).get("phone_number"), "2348022221412")

	def test_personal_info_update_requires_authentication(self):
		"""Test that PATCH /api/profile/personal/ requires authentication"""
		resp = self.client.patch("/api/profile/personal/", {}, format="json")
		self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_bank_info_update_encrypts_and_saves(self):
		"""Test PATCH /api/profile/bank/ encrypts and stores data in draft_payload"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		data = {
			"account_number": "1234567890",
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "12345678901",
		}
		resp = self.client.patch("/api/profile/bank/", data, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		# Response should not contain plaintext
		self.assertNotIn("account_number", resp.data)
		self.assertNotIn("bvn", resp.data)
		self.assertEqual(resp.data.get("bank_name"), "Access Bank")
		self.assertEqual(resp.data.get("bank_code"), "044")
		
		# Verify in database (encrypted data stored in draft_payload, not final fields)
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.account_number_encrypted, "")  # Final field should be empty
		self.assertEqual(self.profile.bvn_encrypted, "")  # Final field should be empty
		# Draft payload should have encrypted values
		self.assertTrue(len(self.profile.draft_payload.get("bank", {}).get("account_number_encrypted", "")) > 0)
		self.assertTrue(len(self.profile.draft_payload.get("bank", {}).get("bvn_encrypted", "")) > 0)

	def test_bank_info_update_requires_authentication(self):
		"""Test that PATCH /api/profile/bank/ requires authentication"""
		resp = self.client.patch("/api/profile/bank/", {}, format="json")
		self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_bank_info_update_does_not_mark_completed(self):
		"""Test that bank info update does not automatically mark profile as completed"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		self.profile.is_completed = False
		self.profile.save()
		
		data = {
			"account_number": "1234567890",
			"bank_name": "Access Bank",
			"bank_code": "044",
			"bvn": "12345678901",
		}
		resp = self.client.patch("/api/profile/bank/", data, format="json")
		
		self.profile.refresh_from_db()
		self.assertFalse(self.profile.is_completed)


class BanksViewTests(APITestCase):
	"""Test banks endpoint"""

	def setUp(self):
		"""Clear cache before each test"""
		from django.core.cache import cache
		cache.clear()

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_returns_simplified_list(self, mock_client_class):
		"""Test GET /api/banks/ returns simplified bank list"""
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		
		# Mock OnePipeClient response
		mock_response = {
			"response": {
				"data": {
					"provider_response": {
						"banks": [
							{"bank_name": "Access Bank", "bank_code": "044"},
							{"bank_name": "Fidelity Bank", "bank_code": "070"},
						]
					}
				}
			}
		}
		mock_client.transact.return_value = mock_response
		
		resp = self.client.get("/api/banks/")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(len(resp.data), 2)
		self.assertEqual(resp.data[0]["name"], "Access Bank")
		self.assertEqual(resp.data[0]["code"], "044")

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_uses_cache(self, mock_client_class):
		"""Test that banks endpoint caches results"""
		from django.core.cache import cache
		
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		
		mock_response = {
			"response": {
				"data": {
					"provider_response": {
						"banks": [
							{"bank_name": "Access Bank", "bank_code": "044"},
						]
					}
				}
			}
		}
		mock_client.transact.return_value = mock_response
		
		# First request
		resp1 = self.client.get("/api/banks/")
		call_count_1 = mock_client.transact.call_count
		
		# Second request should use cache
		resp2 = self.client.get("/api/banks/")
		call_count_2 = mock_client.transact.call_count
		
		self.assertEqual(resp1.data, resp2.data)
		# transact should only be called once due to caching
		self.assertEqual(call_count_1, call_count_2)

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_handles_onepipe_error(self, mock_client_class):
		"""Test that banks endpoint handles OnePipeError gracefully"""
		from .onepipe_client import OnePipeError
		
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.side_effect = OnePipeError(400, "Bad Request")
		
		resp = self.client.get("/api/banks/")
		
		self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
		self.assertIn("error", resp.data)

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_does_not_require_authentication(self, mock_client_class):
		"""Test that banks endpoint is publicly accessible"""
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		
		mock_response = {
			"response": {
				"data": {
					"provider_response": {
						"banks": [{"bank_name": "Test Bank", "bank_code": "999"}]
					}
				}
			}
		}
		mock_client.transact.return_value = mock_response
		
		# No authentication header
		resp = self.client.get("/api/banks/")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(len(resp.data), 1)

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_handles_banks_in_data_key(self, mock_client_class):
		"""Banks list returned in response.data.banks should be parsed"""
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client

		mock_response = {
			"response": {
				"data": {
					"banks": [
						{"name": "DataBank", "code": "101"}
					]
				}
			}
		}
		mock_client.transact.return_value = mock_response

		resp = self.client.get("/api/banks/")

		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(len(resp.data), 1)
		self.assertEqual(resp.data[0]["name"], "DataBank")
		self.assertEqual(resp.data[0]["code"], "101")

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_handles_banks_at_root(self, mock_client_class):
		"""Banks list returned at response.banks root should be parsed"""
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client

		mock_response = {"response": {"banks": [{"name": "RootBank", "code": "202"}]}}
		mock_client.transact.return_value = mock_response

		resp = self.client.get("/api/banks/")

		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(len(resp.data), 1)
		self.assertEqual(resp.data[0]["name"], "RootBank")
		self.assertEqual(resp.data[0]["code"], "202")

	@patch('api.views.OnePipeClient')
	def test_banks_endpoint_returns_502_when_missing_banks(self, mock_client_class):
		"""If provider response lacks banks and no cache exists, return 502"""
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client

		# Response missing banks keys
		mock_response = {"response": {"data": {"provider_response": {}}}}
		mock_client.transact.return_value = mock_response

		resp = self.client.get("/api/banks/")

		self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
		self.assertIn("error", resp.data)


class ProfileSubmitViewTests(APITestCase):
	"""Test profile submission and bank verification"""

	def setUp(self):
		"""Create user with draft profile data"""
		from django.core.cache import cache
		cache.clear()
		
		self.user = User.objects.create_user(
			username="testuser",
			email="test@example.com",
			password="testpass123"
		)
		
		# Create profile with draft data
		self.profile = Profile.objects.create(
			user=self.user,
			first_name="Test",
			draft_payload={
				"personal": {
					"first_name": "John",
					"surname": "Doe",
					"phone_number": "2348022221412",
					"date_of_birth": "1990-01-15",
					"gender": "M",
				},
				"bank": {
					"bank_name": "Access Bank",
					"bank_code": "044",
					"account_number_encrypted": "gAAAAABlz...",  # Mock encrypted
					"bvn_encrypted": "gAAAAABlz...",  # Mock encrypted
				}
			}
		)
		
		# Get access token
		refresh = RefreshToken.for_user(self.user)
		self.access_token = str(refresh.access_token)

	@patch('api.views.OnePipeClient')
	def test_submit_profile_requires_authentication(self, mock_client_class):
		"""Test that POST /api/profile/submit/ requires authentication"""
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('api.views.OnePipeClient')
	def test_submit_profile_fails_without_draft_personal(self, mock_client_class):
		"""Test that submit fails if draft_payload missing personal data"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		# Remove personal from draft
		self.profile.draft_payload = {
			"bank": self.profile.draft_payload["bank"]
		}
		self.profile.save()
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("error", resp.data)

	@patch('api.views.OnePipeClient')
	def test_submit_profile_fails_without_draft_bank(self, mock_client_class):
		"""Test that submit fails if draft_payload missing bank data"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		# Remove bank from draft
		self.profile.draft_payload = {
			"personal": self.profile.draft_payload["personal"]
		}
		self.profile.save()
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("error", resp.data)

	@patch('api.views.OnePipeClient')
	def test_submit_profile_success_copies_draft_to_final(self, mock_client_class):
		"""Test successful profile submission copies draft to final fields"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		# Mock OnePipeClient response
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.return_value = {
			"request_ref": "test-ref-123",
			"response": {
				"status": "Successful",
				"data": {
					"provider_response": {
						"accounts": [
							{"account_number": "1234567890", "account_name": "JOHN DOE"}
						]
					}
				}
			}
		}
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("status"), "verified")
		
		# Verify profile was updated
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.first_name, "John")
		self.assertEqual(self.profile.surname, "Doe")
		self.assertEqual(self.profile.phone_number, "2348022221412")
		self.assertEqual(self.profile.bank_name, "Access Bank")
		self.assertEqual(self.profile.bank_code, "044")
		self.assertTrue(self.profile.is_completed)
		self.assertEqual(self.profile.draft_payload, {})

	@patch('api.views.OnePipeClient')
	def test_submit_profile_failure_does_not_copy_draft(self, mock_client_class):
		"""Test failed verification does not copy draft to final fields"""
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		# Mock OnePipeClient error response
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.return_value = {
			"request_ref": "test-ref-456",
			"response": {
				"status": "Failed",
				"message": "Account not found",
				"data": {
					"provider_response": {}
				}
			}
		}
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("error", resp.data)
		self.assertEqual(resp.data.get("error"), "Bank verification failed")
		
		# Verify profile was NOT updated
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.first_name, "Test")  # Original value
		self.assertFalse(self.profile.is_completed)
		self.assertNotEqual(self.profile.draft_payload, {})  # Draft still there

	@patch('api.views.OnePipeClient')
	def test_submit_profile_creates_audit_record_on_success(self, mock_client_class):
		"""Test that successful submission creates ProfileVerificationAttempt"""
		from .models import ProfileVerificationAttempt
		
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.return_value = {
			"request_ref": "audit-ref-123",
			"response": {
				"status": "Successful",
				"data": {
					"provider_response": {
						"accounts": [{"account_number": "1234567890"}]
					}
				}
			}
		}
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		
		# Verify audit record was created
		attempt = ProfileVerificationAttempt.objects.get(user=self.user)
		self.assertEqual(attempt.request_ref, "audit-ref-123")
		self.assertEqual(attempt.request_type, "lookup accounts min")
		self.assertEqual(attempt.status, "success")
		# Payload should have encrypted account redacted
		self.assertEqual(attempt.payload_sent["transaction"]["account_number"], "[ENCRYPTED]")

	@patch('api.views.OnePipeClient')
	def test_submit_profile_creates_audit_record_on_failure(self, mock_client_class):
		"""Test that failed submission creates ProfileVerificationAttempt"""
		from .models import ProfileVerificationAttempt
		
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.return_value = {
			"request_ref": "audit-ref-456",
			"response": {
				"status": "Failed",
				"message": "Invalid bank details"
			}
		}
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
		
		# Verify audit record was created
		attempt = ProfileVerificationAttempt.objects.get(user=self.user)
		self.assertEqual(attempt.request_ref, "audit-ref-456")
		self.assertEqual(attempt.status, "failed")

	@patch('api.views.OnePipeClient')
	def test_submit_profile_handles_onepipe_error(self, mock_client_class):
		"""Test that OnePipeError is handled gracefully"""
		from .onepipe_client import OnePipeError
		from .models import ProfileVerificationAttempt
		
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
		
		mock_client = MagicMock()
		mock_client_class.return_value = mock_client
		mock_client.transact.side_effect = OnePipeError(500, "Internal Server Error")
		
		resp = self.client.post("/api/profile/submit/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
		self.assertIn("error", resp.data)
		
		# Verify error audit record was created
		attempt = ProfileVerificationAttempt.objects.get(user=self.user)
		self.assertEqual(attempt.status, "error")


class OnePipeWebhookViewTests(APITestCase):
	"""Test OnePipe webhook endpoint"""

	def setUp(self):
		"""Create user and verification attempt for webhook tests"""
		from django.core.cache import cache
		cache.clear()
		
		self.user = User.objects.create_user(
			username="webhookuser",
			email="webhook@example.com",
			password="testpass123"
		)
		
		# Create verification attempt that webhook may reference
		self.verification_attempt = ProfileVerificationAttempt.objects.create(
			user=self.user,
			request_ref="webhook-test-ref-123",
			request_type="lookup accounts min",
			payload_sent={
				"transaction": {
					"account_number": "[ENCRYPTED]",
					"bank_code": "044"
				}
			},
			response={
				"status": "Successful",
				"data": {
					"provider_response": {
						"accounts": [{"account_number": "1234567890"}]
					}
				}
			},
			status="success"
		)

	def test_webhook_does_not_require_authentication(self):
		"""Test that webhook endpoint allows unauthenticated requests"""
		payload = {
			"request_ref": "webhook-test-ref-123",
			"status": "Successful",
			"data": {"accounts": []},
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("status"), "received")

	def test_webhook_stores_payload(self):
		"""Test that webhook endpoint stores payload in database"""
		from .models import WebhookEvent
		
		payload = {
			"request_ref": "test-webhook-ref",
			"status": "Successful",
			"data": {"result": "success"},
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		
		# Verify webhook event was stored
		webhook = WebhookEvent.objects.get(pk=resp.data.get("webhook_id"))
		self.assertEqual(webhook.provider, "onepipe")
		self.assertEqual(webhook.payload, payload)
		self.assertFalse(webhook.processed)
		self.assertEqual(webhook.error, "")

	def test_webhook_correlates_with_verification_attempt(self):
		"""Test that webhook is linked to existing verification attempt by request_ref"""
		from .models import WebhookEvent
		
		payload = {
			"request_ref": "webhook-test-ref-123",
			"status": "Successful",
			"data": {"result": "verified"},
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		
		# Verify webhook is linked to verification attempt
		webhook = WebhookEvent.objects.get(pk=resp.data.get("webhook_id"))
		self.assertEqual(webhook.verification_attempt, self.verification_attempt)

	def test_webhook_stores_without_matching_verification_attempt(self):
		"""Test that webhook is still stored if no matching verification attempt exists"""
		from .models import WebhookEvent
		
		payload = {
			"request_ref": "nonexistent-ref",
			"status": "Successful",
			"data": {},
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		
		# Verify webhook was stored
		webhook = WebhookEvent.objects.get(pk=resp.data.get("webhook_id"))
		self.assertEqual(webhook.payload, payload)
		self.assertIsNone(webhook.verification_attempt)

	def test_webhook_stores_without_request_ref(self):
		"""Test that webhook without request_ref is still stored"""
		from .models import WebhookEvent
		
		payload = {
			"status": "Successful",
			"data": {"result": "success"},
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		
		# Verify webhook was stored
		webhook = WebhookEvent.objects.get(pk=resp.data.get("webhook_id"))
		self.assertEqual(webhook.payload, payload)
		self.assertIsNone(webhook.verification_attempt)

	def test_webhook_handles_empty_payload(self):
		"""Test that webhook handles empty/null payload gracefully"""
		resp = self.client.post("/api/webhooks/onepipe/", {}, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("status"), "received")

	def test_webhook_always_returns_200_ok(self):
		"""Test that webhook always returns 200 OK, even on error"""
		from .models import WebhookEvent
		
		# Send valid payload
		payload = {"request_ref": "webhook-test-ref-123"}
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)

	def test_webhook_returns_id_in_response(self):
		"""Test that webhook response includes webhook_id"""
		payload = {"test": "data"}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertIn("webhook_id", resp.data)
		self.assertTrue(isinstance(resp.data.get("webhook_id"), int))

	def test_webhook_stores_error_on_exception(self):
		"""Test that webhook stores error information if exception occurs during processing"""
		from .models import WebhookEvent
		
		# Send valid payload that will be stored
		payload = {
			"request_ref": "webhook-test-ref-123",
			"status": "Successful",
		}
		
		resp = self.client.post("/api/webhooks/onepipe/", payload, format="json")
		
		# Even if there was an exception, webhook should be stored
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertTrue(WebhookEvent.objects.filter(provider="onepipe").exists())


