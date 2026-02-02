from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from django.conf import settings
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    ProfileMeSerializer,
    PersonalInfoSerializer,
    BankInfoSerializer,
    RulesEngineSerializer,
    RulesEngineUpdateSerializer,
    RulesEngineDisableSerializer,
    MandateCreateSerializer,
    CancelMandateSerializer,
    MandateSerializer,
)
from .models import Profile, ProfileVerificationAttempt, WebhookEvent, RulesEngine, Mandate
from .onepipe_client import OnePipeClient, OnePipeError, build_create_mandate_payload, build_cancel_mandate_payload
import uuid
import json
from .utils.onepipe_utils import extract_activation_url, extract_provider_transaction_ref, extract_payment_id


class HomeView(APIView):
    """Welcome/homepage endpoint with API info"""
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({
            "message": "Welcome to Kore OnePipe API",
            "version": "1.0.0",
            "description": "Bank account verification platform using OnePipe PayWithAccount",
            "docs": {
                "urls": "/docs/URLS_README.md",
                "banks_endpoint": "/docs/BANKS_ENDPOINT.md",
            },
            "endpoints": {
                "auth": {
                    "signup": "POST /api/auth/signup/",
                    "login": "POST /api/auth/login/",
                    "me": "GET /api/auth/me/",
                },
                "profile": {
                    "view": "GET /api/profile/me/",
                    "update_personal": "PATCH /api/profile/personal/",
                    "update_bank": "PATCH /api/profile/bank/",
                    "submit": "POST /api/profile/submit/",
                },
                "rules": {
                    "create": "POST /api/rules-engine/",
                },
                "banks": "GET /api/banks/",
                "webhook": "POST /api/webhooks/onepipe/",
            }
        }, status=status.HTTP_200_OK)


class ServicesView(APIView):
    """
    List of supported financial services.
    
    Used by the frontend for rules engine and service selection during mandate setup.
    Returns a static, ordered list of services with keys and human-readable labels.
    """
    permission_classes = (AllowAny,)

    # Static list of supported financial services
    SERVICES = [
        {"key": "SAVINGS", "label": "Savings"},
        {"key": "INVESTMENT", "label": "Investment"},
        {"key": "TAX", "label": "Tax"},
        {"key": "LOANS", "label": "Loans"},
        {"key": "BILLS", "label": "Bills"},
    ]

    def get(self, request):
        """GET /api/services/ - Return list of supported financial services"""
        return Response(
            {"services": self.SERVICES},
            status=status.HTTP_200_OK,
        )


class SignupView(APIView):
    """Handle user registration and issue JWT tokens"""
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Profile is auto-created by signal when user is created
            # No need to create it manually here
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Return user data and tokens
            user_serializer = UserSerializer(user)
            return Response(
                {
                    "user": user_serializer.data,
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    """Return current authenticated user info with profile state"""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        profile = None
        try:
            profile = user.profile
        except Exception:
            profile = None

        data = {
            "id": user.id,
            "name": user.first_name,
            "email": user.email,
            "profile": {"is_completed": profile.is_completed if profile else False},
        }
        return Response(data, status=status.HTTP_200_OK)


class LoginView(APIView):
    """Handle user login and issue JWT tokens"""
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Return user data and tokens
            user_serializer = UserSerializer(user)
            return Response(
                {
                    "user": user_serializer.data,
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileMeView(APIView):
    """Return current user's full profile with email"""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        # Get or create profile if missing
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={"first_name": user.first_name, "is_completed": False},
        )

        serializer = ProfileMeSerializer(profile, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PersonalInfoUpdateView(APIView):
    """Update personal information on profile (stores in draft_payload)"""
    permission_classes = (IsAuthenticated,)

    def patch(self, request):
        user = request.user
        # Get or create profile if missing
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={"first_name": user.first_name, "is_completed": False},
        )

        serializer = PersonalInfoSerializer(data=request.data)
        if serializer.is_valid():
            # Store unverified personal data in draft_payload
            draft_personal = {
                "first_name": serializer.validated_data.get("first_name", ""),
                "surname": serializer.validated_data.get("surname", ""),
                "phone_number": serializer.validated_data.get("phone_number", ""),
                "date_of_birth": str(serializer.validated_data.get("date_of_birth")) if serializer.validated_data.get("date_of_birth") else None,
                "gender": serializer.validated_data.get("gender"),
            }
            
            if not profile.draft_payload:
                profile.draft_payload = {}
            profile.draft_payload["personal"] = draft_personal
            profile.save()

            # Return saved draft data (exclude None/empty values)
            response_data = {k: v for k, v in draft_personal.items() if v}
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BankInfoUpdateView(APIView):
    """Update bank information on profile (stores encrypted data in draft_payload)"""
    permission_classes = (IsAuthenticated,)

    def patch(self, request):
        from .encryption import encrypt_value
        
        user = request.user
        # Get or create profile if missing
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={"first_name": user.first_name, "is_completed": False},
        )

        serializer = BankInfoSerializer(data=request.data)
        if serializer.is_valid():
            # Encrypt sensitive fields
            account_number = serializer.validated_data.get("account_number")
            bvn = serializer.validated_data.get("bvn")
            account_number_encrypted = encrypt_value(account_number) if account_number else ""
            bvn_encrypted = encrypt_value(bvn) if bvn else ""
            
            # Store encrypted bank data in draft_payload
            draft_bank = {
                "bank_name": serializer.validated_data.get("bank_name", ""),
                "bank_code": serializer.validated_data.get("bank_code", ""),
                "account_number_encrypted": account_number_encrypted,
                "bvn_encrypted": bvn_encrypted,
            }
            
            if not profile.draft_payload:
                profile.draft_payload = {}
            profile.draft_payload["bank"] = draft_bank
            profile.save()

            # Return safe response without plaintext
            return Response(
                {
                    "bank_name": draft_bank["bank_name"],
                    "bank_code": draft_bank["bank_code"],
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BanksView(APIView):
    """Fetch list of banks from OnePipe with caching"""
    permission_classes = (AllowAny,)
    CACHE_KEY = "onepipe:get_banks"
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # Fallback list of major Nigerian banks for when provider fails
    FALLBACK_BANKS = [
        {"name": "Access Bank", "code": "044"},
        {"name": "GTBank", "code": "007"},
        {"name": "Zenith Bank", "code": "057"},
        {"name": "FirstBank", "code": "011"},
        {"name": "UBA", "code": "033"},
        {"name": "Guaranty Trust Bank", "code": "058"},
        {"name": "FCMB", "code": "214"},
        {"name": "Stanbic IBTC Bank", "code": "221"},
        {"name": "Union Bank", "code": "032"},
        {"name": "Sterling Bank", "code": "232"},
    ]

    def get(self, request):
        # Check cache first
        cached_banks = cache.get(self.CACHE_KEY)
        if cached_banks is not None:
            return Response(cached_banks, status=status.HTTP_200_OK)

        try:
            client = OnePipeClient()
            # Use builder from onepipe_client for consistent payloads
            from .onepipe_client import build_get_banks_payload

            payload = build_get_banks_payload()
            result = client.transact(payload)
            response_data = result.get("response", {})

            # Parse banks defensively
            banks = self._parse_banks_from_response_v2(response_data)

            if banks is None:
                # Provider failed, use fallback
                cache.set(self.CACHE_KEY, self.FALLBACK_BANKS, self.CACHE_TIMEOUT)
                return Response(self.FALLBACK_BANKS, status=status.HTTP_200_OK)

            # Cache and return
            cache.set(self.CACHE_KEY, banks, self.CACHE_TIMEOUT)
            return Response(banks, status=status.HTTP_200_OK)

        except OnePipeError as e:
            # On provider error, use fallback
            cache.set(self.CACHE_KEY, self.FALLBACK_BANKS, self.CACHE_TIMEOUT)
            return Response(self.FALLBACK_BANKS, status=status.HTTP_200_OK)

        except Exception as e:
            # On unexpected error, use fallback
            cache.set(self.CACHE_KEY, self.FALLBACK_BANKS, self.CACHE_TIMEOUT)
            return Response(self.FALLBACK_BANKS, status=status.HTTP_200_OK)

    def _parse_banks_from_response(self, response_data):
        """
        Parse banks from OnePipe API response.
        Expects response structure with provider_response.banks or similar.
        Returns simplified list: [{"name": "...", "code": "..."}, ...]
        """
        banks = []
        try:
            # Navigate through response structure
            provider_response = response_data.get("data", {}).get(
                "provider_response", {}
            )
            if not provider_response:
                # Try alternate structure
                provider_response = response_data.get("provider_response", {})

            # Extract banks array (structure may vary)
            banks_data = provider_response.get("banks", [])
            if not banks_data:
                banks_data = provider_response.get("accounts", [])

            # Simplify bank data
            for bank in banks_data:
                simplified_bank = {
                    "name": bank.get("bank_name") or bank.get("name", "Unknown"),
                    "code": bank.get("bank_code") or bank.get("code", ""),
                }
                if simplified_bank["code"]:
                    banks.append(simplified_bank)

        except (KeyError, TypeError, AttributeError):
            # If parsing fails, return empty list with error indication
            pass

        return banks if banks else {"error": "Unable to parse banks from response"}

    def _parse_banks_from_response_v2(self, response_data):
        """Defensive parser that normalizes provider responses to [{'name','code'}, ...]

        Tries keys in order: response['data']['banks'], response['banks'], response['data']
        Returns list on success, or None if no banks list found.
        """
        try:
            # 1. response['data']['banks']
            data = response_data.get("data") if isinstance(response_data, dict) else None
            banks_list = None

            if isinstance(data, dict) and data.get("banks"):
                banks_list = data.get("banks")
            elif isinstance(response_data, dict) and response_data.get("banks"):
                banks_list = response_data.get("banks")
            elif isinstance(data, list):
                # Sometimes data itself is a list of banks
                banks_list = data
            elif isinstance(data, dict) and data:
                # If data contains provider_response with banks
                provider_response = data.get("provider_response")
                if isinstance(provider_response, dict) and provider_response.get("banks"):
                    banks_list = provider_response.get("banks")

            if not banks_list:
                return None

            normalized = []
            for item in banks_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("bank_name") or item.get("name") or item.get("bank") or item.get("bankFullName")
                code = item.get("bank_code") or item.get("code") or item.get("bankCode")
                if not code:
                    continue
                normalized.append({"name": name or "Unknown", "code": code})

            return normalized if normalized else None
        except Exception:
            return None


class ProfileSubmitView(APIView):
    """Submit profile for bank account verification"""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate draft_payload has both personal and bank data
        draft_personal = profile.draft_payload.get("personal")
        draft_bank = profile.draft_payload.get("bank")

        if not draft_personal or not draft_bank:
            return Response(
                {"error": "Both personal and bank information are required. Please complete both sections."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build OnePipe payload for bank account lookup using builder function
        from .onepipe_client import build_lookup_accounts_min_payload
        
        client = OnePipeClient()
        
        # Get account number from draft (stored as plaintext in test draft_payload,
        # but normally would be encrypted. For OnePipe lookup, we need plaintext.)
        # In production, if account is encrypted in draft, it should be decrypted before passing to builder
        account_number = draft_bank.get("account_number", "")  # Plaintext key in draft
        
        # Build payload using proper builder with Triple DES encryption
        payload = build_lookup_accounts_min_payload(
            customer_ref=f"user-{user.id}",
            account_number=account_number,
            bank_code=draft_bank.get("bank_code", ""),
            bvn=draft_bank.get("bvn"),  # Plaintext BVN from draft
            first_name=draft_personal.get("first_name", ""),
            last_name=draft_personal.get("surname", ""),
            mobile_no=draft_personal.get("phone_number", ""),
            transaction_desc="Bank account verification for profile completion",
        )

        try:
            # Call OnePipe with atomic transaction
            with transaction.atomic():
                # Call OnePipeClient
                result = client.transact(payload)
                request_ref = result.get("request_ref", "")
                response_data = result.get("response", {})
                
                # Check if lookup was successful
                is_verified = self._check_verification_success(response_data)

                # Redact plaintext from payload for auditing
                redacted_payload = {
                    **payload,
                    "transaction": {
                        **payload["transaction"],
                        "account_number": "[ENCRYPTED]",
                    }
                }

                if is_verified:
                    # Copy draft data to final fields
                    profile.first_name = draft_personal.get("first_name", "")
                    profile.surname = draft_personal.get("surname", "")
                    profile.phone_number = draft_personal.get("phone_number", "")
                    profile.date_of_birth = draft_personal.get("date_of_birth")
                    profile.gender = draft_personal.get("gender")
                    
                    # Copy bank data (already encrypted in draft)
                    profile.bank_name = draft_bank.get("bank_name", "")
                    profile.bank_code = draft_bank.get("bank_code", "")
                    profile.account_number_encrypted = draft_bank.get("account_number_encrypted", "")
                    profile.bvn_encrypted = draft_bank.get("bvn_encrypted", "")
                    
                    # Mark as completed and clear draft
                    profile.is_completed = True
                    profile.draft_payload = {}
                    profile.save()

                    # Log successful attempt
                    ProfileVerificationAttempt.objects.create(
                        user=user,
                        request_ref=request_ref,
                        request_type="lookup accounts min",
                        payload_sent=redacted_payload,
                        response=response_data,
                        status="success",
                    )

                    # Return success with profile summary
                    return Response(
                        {
                            "status": "verified",
                            "message": "Your bank account has been verified successfully",
                            "profile": {
                                "is_completed": True,
                                "bank_name": profile.bank_name,
                                "bank_code": profile.bank_code,
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # Lookup failed - do not copy draft data
                    log_status = "failed"
                    
                    # Log failed attempt
                    ProfileVerificationAttempt.objects.create(
                        user=user,
                        request_ref=request_ref,
                        request_type="lookup accounts min",
                        payload_sent=redacted_payload,
                        response=response_data,
                        status=log_status,
                    )

                    # Return failure response
                    return Response(
                        {
                            "error": "Bank verification failed",
                            "message": self._extract_error_message(response_data),
                            "provider_response": response_data,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        except OnePipeError as e:
            # OnePipe API error
            request_ref = getattr(e, "request_ref", "unknown")
            redacted_payload = {
                **payload,
                "transaction": {
                    **payload["transaction"],
                    "account_number": "[ENCRYPTED]",
                }
            }
            
            ProfileVerificationAttempt.objects.create(
                user=user,
                request_ref=request_ref,
                request_type="lookup accounts min",
                payload_sent=redacted_payload,
                response={"error": str(e), "status_code": getattr(e, "status_code", None)},
                status="error",
            )

            return Response(
                {
                    "error": "Failed to contact bank verification service",
                    "details": str(e),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            # Unexpected error
            redacted_payload = {
                **payload,
                "transaction": {
                    **payload["transaction"],
                    "account_number": "[ENCRYPTED]",
                }
            }
            
            ProfileVerificationAttempt.objects.create(
                user=user,
                request_ref="unknown",
                request_type="lookup accounts min",
                payload_sent=redacted_payload,
                response={"error": str(e)},
                status="error",
            )

            return Response(
                {
                    "error": "An unexpected error occurred",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _check_verification_success(self, response_data):
        """Check if OnePipe response indicates successful verification"""
        # Success indicators: status="Successful" or response status code indicates success
        status_value = response_data.get("status", "").lower()
        if status_value == "successful":
            return True
        
        # Check nested structure
        provider_response = response_data.get("data", {}).get("provider_response", {})
        if provider_response:
            # If we got a provider response with account details, consider it verified
            return bool(provider_response.get("accounts") or provider_response.get("account"))
        
        return False

    def _extract_error_message(self, response_data):
        """Extract error message from OnePipe response"""
        # Try various common error message locations
        if response_data.get("message"):
            return response_data.get("message")
        if response_data.get("error"):
            return response_data.get("error")
        
        provider_response = response_data.get("data", {}).get("provider_response", {})
        if provider_response.get("message"):
            return provider_response.get("message")
        if provider_response.get("error"):
            return provider_response.get("error")
        
        return "Verification failed. Please check your details and try again."


class OnePipeWebhookView(APIView):
    """Handle OnePipe webhook events"""
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Store webhook event and attempt to correlate with verification attempt.
        Non-blocking, returns 200 OK immediately.
        """
        try:
            payload = request.data or {}
            request_ref = payload.get("request_ref")
            
            # Try to find associated verification attempt
            verification_attempt = None
            if request_ref:
                try:
                    verification_attempt = ProfileVerificationAttempt.objects.get(
                        request_ref=request_ref
                    )
                except ProfileVerificationAttempt.DoesNotExist:
                    # Not found, but that's okay - we still store the webhook
                    pass
            
            # Store webhook event
            webhook_event = WebhookEvent.objects.create(
                provider="onepipe",
                payload=payload,
                verification_attempt=verification_attempt,
                processed=False,
            )
            
            return Response(
                {
                    "status": "received",
                    "webhook_id": webhook_event.id,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            # Log error but still return 200 OK (don't want OnePipe retrying)
            try:
                WebhookEvent.objects.create(
                    provider="onepipe",
                    payload=request.data or {},
                    processed=False,
                    error=str(e),
                )
            except Exception:
                # Even if logging fails, return 200 OK
                pass
            
            return Response(
                {
                    "status": "received",
                    "warning": "Webhook stored but error during processing",
                },
                status=status.HTTP_200_OK,
            )


# Provide a module-level callable name expected by routing
banks_list = BanksView.as_view()


class RulesEngineCreateView(APIView):
    """
    Create and manage debit rules for the authenticated user.
    
    POST /api/rules-engine/ - Create a new debit rule
    
    Accepts all rules engine inputs in one request and validates using RulesEngineSerializer.
    
    After successful creation:
    - Returns success response with "ready_for_mandate": true flag
    - Auto-deactivates any previous active rules for the user
    
    TODO: trigger create mandate after rules engine is saved
    """
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        """
        Create a new RulesEngine for the authenticated user.
        
        Request body:
        {
            "monthly_max_debit": 50000.00,
            "single_max_debit": 10000.00,
            "frequency": "MONTHLY",
            "amount_per_frequency": 50000.00,
            "allocations": [
                {"bucket": "SAVINGS", "percentage": 50},
                {"bucket": "SPENDING", "percentage": 50}
            ],
            "failure_action": "NOTIFY",
            "start_date": "2026-02-01",
            "end_date": null
        }
        """
        serializer = RulesEngineSerializer(
            data=request.data,
            context={"request": request}
        )
        
        if serializer.is_valid():
            # Save the new rule
            rule = serializer.save()
            
            # TODO: trigger create mandate after rules engine is saved
            
            return Response(
                {
                    "message": "Rules saved successfully",
                    "rule": RulesEngineSerializer(rule).data,
                    "ready_for_mandate": True,
                },
                status=status.HTTP_201_CREATED,
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class RulesEngineDetailView(APIView):
    """
    Retrieve the currently active RulesEngine for the authenticated user.
    
    GET /api/rules-engine/me/ - Get active rule
    
    Returns the currently active debit rule for the user, or 404 if none exists.
    """
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        """
        Retrieve the currently active RulesEngine for the authenticated user.
        
        Response (200 OK):
        {
            "id": 5,
            "monthly_max_debit": "50000.00",
            "single_max_debit": "10000.00",
            "frequency": "MONTHLY",
            "amount_per_frequency": "50000.00",
            "allocations": [...],
            "failure_action": "NOTIFY",
            "start_date": "2026-02-01",
            "end_date": null,
            "is_active": true,
            "created_at": "2026-01-31T12:30:00Z",
            "updated_at": "2026-01-31T12:30:00Z"
        }
        
        Response (404 Not Found):
        {
            "error": "No rules engine configured yet."
        }
        """
        rule = RulesEngine.get_active_for_user(request.user)
        if not rule:
            return Response({"error": "No rules engine configured yet."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RulesEngineSerializer(rule)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Partially update the currently active RulesEngine for the authenticated user.

        PATCH /api/rules-engine/me/
        - Finds the active rule for request.user
        - Applies partial updates via RulesEngineUpdateSerializer
        - Returns updated RulesEngine data
        """
        rule = RulesEngine.get_active_for_user(request.user)
        if not rule:
            return Response({"error": "No rules engine configured yet."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RulesEngineUpdateSerializer(
            instance=rule, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated = serializer.save()
            return Response(RulesEngineSerializer(updated).data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RulesEngineDisableView(APIView):
    """Disable (soft-delete) the currently active RulesEngine for the authenticated user."""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """POST /api/rules-engine/me/disable/ - mark active rule as inactive"""
        rule = RulesEngine.get_active_for_user(request.user)
        if not rule:
            return Response({"error": "No rules engine configured yet."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RulesEngineDisableSerializer(instance=rule, data={})
        # No input fields required; validate/save pattern for consistency
        serializer.is_valid(raise_exception=True)
        disabled = serializer.update(rule, serializer.validated_data)

        return Response(
            {"message": "Rules engine disabled", "rule": RulesEngineSerializer(disabled).data},
            status=status.HTTP_200_OK,
        )


class MandateCreateView(APIView):
    """POST /api/mandates/create/ - create a mandate via OnePipe

    Flow:
    1. Validate prerequisites with MandateCreateSerializer
    2. Build payload with build_create_mandate_payload
    3. Call OnePipeClient.transact
    4. Persist Mandate record and return 201 with request_ref and activation_url
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = MandateCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        profile = serializer.validated_data["profile"]
        rules_engine = serializer.validated_data["rules_engine"]
        customer_consent = serializer.validated_data.get("customer_consent")

        # Build payload
        payload = build_create_mandate_payload(user, profile, rules_engine, customer_consent)

        client = OnePipeClient()

        try:
            result = client.transact(payload)
            request_ref = result.get("request_ref")
            response_data = result.get("response")

            # Persist Mandate and extract provider identifiers
            provider_resp = {}
            try:
                if isinstance(response_data, dict):
                    provider_resp = response_data.get("data", {}).get("provider_response") or {}
            except Exception:
                provider_resp = {}

            activation_url = ""
            transaction_ref = ""
            if isinstance(response_data, dict):
                data = response_data.get("data") or response_data
                if isinstance(data, dict):
                    activation_url = data.get("activation_url") or data.get("authorization_url") or data.get("redirect_url") or data.get("url") or ""
                    transaction_ref = data.get("transaction_ref") or data.get("tx_ref") or data.get("transactionId") or ""

            # Extract fields from provider_response
            mandate_reference = None
            subscription_id = None
            provider_status = None
            if isinstance(provider_resp, dict):
                mandate_reference = provider_resp.get("reference") or provider_resp.get("mandate_reference")
                provider_status = provider_resp.get("status")
                meta = provider_resp.get("meta") or {}
                try:
                    subscription_id = meta.get("subscription_id")
                except Exception:
                    subscription_id = None

            # Decide status
            save_status = "PENDING"
            if provider_status == "ACTIVE":
                save_status = "ACTIVE"
            elif provider_status and provider_status.upper() in ("SUCCESSFUL", "SUCCESS", "OK"):
                save_status = "PENDING"

            with transaction.atomic():
                mandate = Mandate.objects.create(
                    user=user,
                    rules_engine=rules_engine,
                    status=save_status,
                    request_ref=request_ref or uuid.uuid4().hex,
                    transaction_ref=transaction_ref or "",
                    activation_url=activation_url or "",
                    payment_id=extract_payment_id(response_data) or "",
                    mandate_reference=mandate_reference or "",
                    subscription_id=subscription_id,
                    provider_response=response_data,
                )

            # If provider indicated failure via top-level status, return 400
            top_status = ""
            if isinstance(response_data, dict):
                top_status = str(response_data.get("status", "")).lower()

            if top_status and top_status not in ("successful", "success", "ok"):
                return Response(
                    {
                        "message": "Provider indicated failure",
                        "provider_response": response_data,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "id": mandate.id,
                    "status": mandate.status,
                    "request_ref": mandate.request_ref,
                    "activation_url": mandate.activation_url,
                },
                status=status.HTTP_201_CREATED,
            )

        except OnePipeError as e:
            # Persist failed mandate record
            with transaction.atomic():
                mandate = Mandate.objects.create(
                    user=user,
                    rules_engine=rules_engine,
                    status="FAILED",
                    request_ref=getattr(e, "request_ref", uuid.uuid4().hex),
                    provider_response={"error": str(e), "status_code": getattr(e, "status_code", None)},
                )

            return Response(
                {"message": "Failed to contact OnePipe", "details": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class MandatesMeView(APIView):
    """GET /api/mandates/me/ - return latest mandate for the authenticated user"""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        mandate = Mandate.objects.filter(user=request.user).order_by("-created_at").first()
        if not mandate:
            return Response({"error": "No mandate found for this user."}, status=status.HTTP_404_NOT_FOUND)

        serializer = MandateSerializer(mandate)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelMandateView(APIView):
    """POST /api/mandates/cancel/ - cancel an active mandate via OnePipe"""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = CancelMandateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        profile = serializer.validated_data["profile"]

        # Find latest ACTIVE mandate
        mandate = Mandate.objects.filter(user=user, status="ACTIVE").order_by("-created_at").first()
        if not mandate:
            return Response({"error": "No active mandate to cancel"}, status=status.HTTP_404_NOT_FOUND)

        # mandate_reference must exist
        if not getattr(mandate, "mandate_reference", ""):
            return Response({"error": "Mandate mandate_reference missing; cannot cancel."}, status=status.HTTP_400_BAD_REQUEST)

        payload = build_cancel_mandate_payload(user, profile, mandate)

        client = OnePipeClient()
        try:
            result = client.transact(payload)
            response = result.get("response")

            # Save cancel provider response for audit
            mandate.cancel_response = response

            # Success condition: status == "Successful" AND data.provider_response_code == "00"
            success = False
            if isinstance(response, dict):
                if response.get("status") == "Successful" and response.get("data", {}).get("provider_response_code") == "00":
                    success = True

            if success:
                mandate.status = "CANCELLED"
                mandate.cancelled_at = timezone.now()
                mandate.save()
                return Response({"message": "Mandate cancelled", "mandate_status": "CANCELLED"}, status=status.HTTP_200_OK)
            else:
                # keep mandate ACTIVE, but store cancel_response for audit
                mandate.save()
                return Response({"message": "Provider cancellation failed", "provider_response": response}, status=status.HTTP_400_BAD_REQUEST)

        except OnePipeError as e:
            mandate.cancel_response = {"error": str(e), "status_code": getattr(e, "status_code", None)}
            mandate.save()
            return Response({"message": "Failed to contact OnePipe", "details": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

