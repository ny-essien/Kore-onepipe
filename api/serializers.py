from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from datetime import date
from .models import RulesEngine, Mandate, Profile
import uuid
import re


class UserSerializer(serializers.ModelSerializer):
    """Serializer for returning user data"""
    name = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "name", "email")
        read_only_fields = ("id",)


class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=True, write_only=True, label="Full name")
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "password", "confirm_password")

    def validate_email(self, value):
        """Validate that email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_password(self, value):
        """Validate password using Django password validators"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, data):
        """Validate that password and confirm_password match"""
        if data.get("password") != data.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data

    def create(self, validated_data):
        """Create a new user with email as username"""
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["full_name"],
            password=validated_data["password"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    def validate(self, data):
        """Authenticate user by email and password"""
        email = data.get("email")
        password = data.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials.")

        data["user"] = user
        return data


class ProfileMeSerializer(serializers.Serializer):
    """Read-only serializer for current user profile with email"""
    email = serializers.SerializerMethodField()
    first_name = serializers.CharField(read_only=True)
    surname = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    date_of_birth = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    bank_name = serializers.CharField(read_only=True)
    bank_code = serializers.CharField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    def get_email(self, obj):
        """Extract email from request.user context"""
        user = self.context["request"].user
        return user.email


class PersonalInfoSerializer(serializers.Serializer):
    """Serializer for updating personal information"""
    first_name = serializers.CharField(required=False, max_length=255, allow_blank=True)
    surname = serializers.CharField(required=False, max_length=255, allow_blank=True)
    phone_number = serializers.CharField(required=False, max_length=20, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        required=False,
        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
        allow_null=True,
    )

    def validate_phone_number(self, value):
        """Validate phone number format (non-empty digits)"""
        if value and not value.replace(" ", "").replace("-", "").isdigit():
            raise serializers.ValidationError(
                "Phone number must contain only digits, spaces, and hyphens."
            )
        return value

    def validate_date_of_birth(self, value):
        """Validate that date of birth is in the past"""
        from django.utils import timezone
        if value:
            today = timezone.now().date()
            if value >= today:
                raise serializers.ValidationError("Date of birth must be in the past.")
        return value


class BankInfoSerializer(serializers.Serializer):
    """Serializer for updating bank information with encryption"""
    account_number = serializers.CharField(required=True, max_length=20, write_only=True)
    bank_name = serializers.CharField(required=True, max_length=255)
    bank_code = serializers.CharField(required=True, max_length=10)
    bvn = serializers.CharField(required=True, max_length=15, write_only=True)

    def validate_account_number(self, value):
        """Validate account number is 10 digits"""
        digits_only = value.replace(" ", "")
        if len(digits_only) != 10 or not digits_only.isdigit():
            raise serializers.ValidationError(
                "Account number must be exactly 10 digits."
            )
        return digits_only

    def validate_bvn(self, value):
        """Validate BVN is 11 digits (Nigeria BVN)"""
        digits_only = value.replace(" ", "")
        if len(digits_only) != 11 or not digits_only.isdigit():
            raise serializers.ValidationError(
                "BVN must be exactly 11 digits (Nigeria standard)."
            )
        return digits_only

    def validate_bank_code(self, value):
        """Validate bank code is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Bank code is required.")
        return value

    def save(self, profile):
        """Encrypt sensitive fields and update profile"""
        from .encryption import encrypt_value

        account_number = self.validated_data.get("account_number")
        bvn = self.validated_data.get("bvn")
        bank_name = self.validated_data.get("bank_name")
        bank_code = self.validated_data.get("bank_code")

        # Encrypt sensitive fields
        if account_number:
            profile.account_number_encrypted = encrypt_value(account_number)
        if bvn:
            profile.bvn_encrypted = encrypt_value(bvn)
        if bank_name:
            profile.bank_name = bank_name
        if bank_code:
            profile.bank_code = bank_code

        profile.save()
        return profile


class RulesEngineSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating debit rules.
    
    Responsibilities:
    - Validate all numeric fields are positive
    - Validate frequency is an allowed choice
    - Validate allocations structure and percentages
    - Validate date range
    - Auto-attach current user on create
    - Deactivate existing active rules before creating new one
    """
    
    class Meta:
        model = RulesEngine
        fields = (
            "id",
            "monthly_max_debit",
            "single_max_debit",
            "frequency",
            "amount_per_frequency",
            "allocations",
            "failure_action",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "is_active")
    
    def validate_monthly_max_debit(self, value):
        """Validate monthly_max_debit is positive"""
        if value <= 0:
            raise serializers.ValidationError("monthly_max_debit must be greater than 0.")
        return value
    
    def validate_single_max_debit(self, value):
        """Validate single_max_debit is positive"""
        if value <= 0:
            raise serializers.ValidationError("single_max_debit must be greater than 0.")
        return value
    
    def validate_amount_per_frequency(self, value):
        """Validate amount_per_frequency is positive"""
        if value <= 0:
            raise serializers.ValidationError("amount_per_frequency must be greater than 0.")
        return value
    
    def validate_frequency(self, value):
        """Validate frequency is one of the allowed choices"""
        allowed_frequencies = [choice[0] for choice in RulesEngine.FREQUENCY_CHOICES]
        if value not in allowed_frequencies:
            raise serializers.ValidationError(
                f"frequency must be one of: {', '.join(allowed_frequencies)}"
            )
        return value
    
    def validate_failure_action(self, value):
        """Validate failure_action is one of the allowed choices"""
        allowed_actions = [choice[0] for choice in RulesEngine.FAILURE_ACTION_CHOICES]
        if value not in allowed_actions:
            raise serializers.ValidationError(
                f"failure_action must be one of: {', '.join(allowed_actions)}"
            )
        return value
    
    def validate_start_date(self, value):
        """Validate start_date is not in the past"""
        if value < date.today():
            raise serializers.ValidationError("start_date cannot be in the past.")
        return value
    
    def validate_allocations(self, value):
        """
        Validate allocations structure:
        - Must be a non-empty list
        - Each item must have 'bucket' and 'percentage' keys
        - Percentage must be between 1 and 100
        - Total percentage must equal exactly 100
        """
        if not value:
            raise serializers.ValidationError("allocations cannot be empty.")
        
        if not isinstance(value, list):
            raise serializers.ValidationError("allocations must be a list.")
        
        total_percentage = 0
        
        for idx, allocation in enumerate(value):
            if not isinstance(allocation, dict):
                raise serializers.ValidationError(
                    f"allocations[{idx}] must be an object/dictionary."
                )
            
            # Check required keys
            if "bucket" not in allocation:
                raise serializers.ValidationError(
                    f"allocations[{idx}] missing required key 'bucket'."
                )
            
            if "percentage" not in allocation:
                raise serializers.ValidationError(
                    f"allocations[{idx}] missing required key 'percentage'."
                )
            
            # Validate bucket is a string
            if not isinstance(allocation["bucket"], str) or not allocation["bucket"]:
                raise serializers.ValidationError(
                    f"allocations[{idx}]['bucket'] must be a non-empty string."
                )
            
            # Validate percentage is a number
            try:
                percentage = float(allocation["percentage"])
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"allocations[{idx}]['percentage'] must be a number."
                )
            
            # Validate percentage is between 1 and 100
            if percentage < 1 or percentage > 100:
                raise serializers.ValidationError(
                    f"allocations[{idx}]['percentage'] must be between 1 and 100."
                )
            
            total_percentage += percentage
        
        # Validate total percentage equals 100
        if total_percentage != 100:
            raise serializers.ValidationError(
                f"Total percentage of allocations must equal 100, got {total_percentage}."
            )
        
        return value
    
    def validate(self, data):
        """Validate date relationships and other cross-field validations"""
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        
        # Validate end_date is after start_date if provided
        if end_date and start_date and end_date <= start_date:
            raise serializers.ValidationError({
                "end_date": "end_date must be after start_date."
            })
        
        # Validate single_max_debit is not greater than monthly_max_debit
        monthly_max = data.get("monthly_max_debit")
        single_max = data.get("single_max_debit")
        
        if monthly_max and single_max and single_max > monthly_max:
            raise serializers.ValidationError({
                "single_max_debit": "single_max_debit cannot be greater than monthly_max_debit."
            })
        
        return data
    
    def create(self, validated_data):
        """
        Create a new RulesEngine instance.
        
        On create:
        - Automatically attach the current user
        - Deactivate any existing active RulesEngine for this user
        """
        # Get the user from the request context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated to create rules.")
        
        user = request.user
        
        # Deactivate any existing active rules for this user
        RulesEngine.objects.filter(user=user, is_active=True).update(is_active=False)
        
        # Create the new rule with the user attached
        validated_data["user"] = user
        return super().create(validated_data)


class RulesEngineUpdateSerializer(RulesEngineSerializer):
    """Serializer for partial updates (PATCH) of an existing RulesEngine.

    - Allows partial updates for numeric, frequency, allocations, failure_action and dates.
    - Reuses validation from `RulesEngineSerializer`.
    - Does not allow changing the `user` or timestamps.
    - Ignores `is_active` if present in the payload.
    """

    class Meta(RulesEngineSerializer.Meta):
        # Reuse same fields but make user and timestamps read-only; is_active not writable here
        read_only_fields = ("id", "created_at", "updated_at", "is_active", "user")

    def update(self, instance, validated_data):
        # Ensure user cannot be changed via payload
        validated_data.pop("user", None)

        # Ignore attempts to set is_active through this serializer
        validated_data.pop("is_active", None)

        # Delegate to parent for field-level validations and update
        return super(RulesEngineSerializer, self).update(instance, validated_data)


class RulesEngineDisableSerializer(serializers.Serializer):
    """Serializer used to disable (soft-delete) a RulesEngine by setting `is_active=False`.

    No input fields are required. Use as:
        serializer = RulesEngineDisableSerializer(instance=rule, data={})
        serializer.is_valid(raise_exception=True)
        serializer.save()
    """

    def update(self, instance, validated_data):
        instance.is_active = False
        instance.save()
        return instance

    def create(self, validated_data):
        raise NotImplementedError("Use this serializer with an existing instance to disable it.")


class MandateCreateSerializer(serializers.Serializer):
    """Create a Mandate for the authenticated user using their profile and
    the active RulesEngine.

    Inputs:
      - customer_consent: optional base64 string (allow empty)

    On success creates a `Mandate` record with status 'PENDING' and returns
    summary fields: id, status, request_ref, activation_url, provider_response.
    """

    customer_consent = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to create a mandate.")

        user = request.user

        # Ensure profile exists and is completed
        profile = getattr(user, "profile", None)
        if profile is None:
            raise serializers.ValidationError("User profile not found. Complete your profile before creating a mandate.")
        if not getattr(profile, "is_completed", False):
            raise serializers.ValidationError("User profile is not completed. Please complete your profile before creating a mandate.")

        # Ensure active rules engine exists
        rules_engine = RulesEngine.get_active_for_user(user)
        if rules_engine is None or not rules_engine.is_active:
            raise serializers.ValidationError("No active RulesEngine found for user. Configure rules before creating a mandate.")

        # Check required profile fields
        missing = []
        if not profile.first_name:
            missing.append("first_name")
        if not profile.surname:
            missing.append("surname")
        phone = getattr(profile, "phone_number", "")
        if not phone:
            missing.append("phone_number")
        if not getattr(profile, "bank_code", ""):
            missing.append("bank_code")
        if not getattr(profile, "account_number_encrypted", ""):
            missing.append("account_number_encrypted")
        if not getattr(profile, "bvn_encrypted", ""):
            missing.append("bvn_encrypted")

        if missing:
            raise serializers.ValidationError({"profile": f"Missing required profile fields: {', '.join(missing)}"})

        # Validate phone format: 13 digits starting with '234'
        if not re.match(r"^234\d{10}$", phone):
            raise serializers.ValidationError({"phone_number": "phone_number must be 13 digits and start with '234' (e.g. 2348012345678)."})

        # Attach validated objects for use in create()
        data["user"] = user
        data["profile"] = profile
        data["rules_engine"] = rules_engine
        return data

    def create(self, validated_data):
        user = validated_data["user"]
        rules_engine = validated_data["rules_engine"]

        # Create Mandate record in PENDING state; provider interaction happens elsewhere
        mandate = Mandate.objects.create(
            user=user,
            rules_engine=rules_engine,
            status="PENDING",
            request_ref=uuid.uuid4().hex,
        )

        return mandate

    def to_representation(self, instance):
        # instance is a Mandate
        provider_summary = {}
        if instance.provider_response:
            # Try to summarise common keys
            if isinstance(instance.provider_response, dict):
                for key in ("status", "message", "result", "data"):
                    if key in instance.provider_response:
                        provider_summary[key] = instance.provider_response[key]
            else:
                provider_summary = {"raw": instance.provider_response}

        return {
            "id": instance.id,
            "status": instance.status,
            "request_ref": instance.request_ref,
            "activation_url": instance.activation_url or "",
            "provider_response": provider_summary,
        }


class CancelMandateSerializer(serializers.Serializer):
    """Serializer to validate prerequisites for cancelling a mandate."""

    # No inputs required

    def validate(self, data):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        user = request.user
        profile = getattr(user, "profile", None)
        if profile is None:
            raise serializers.ValidationError("User profile not found.")

        # Ensure required profile fields
        missing = []
        if not profile.first_name:
            missing.append("first_name")
        if not profile.surname:
            missing.append("surname")
        if not getattr(profile, "phone_number", ""):
            missing.append("phone_number")

        if missing:
            raise serializers.ValidationError({"profile": f"Missing profile fields: {', '.join(missing)}"})

        # Validate phone format
        import re
        phone = getattr(profile, "phone_number", "")
        if not re.match(r"^234\d{10}$", phone):
            raise serializers.ValidationError({"phone_number": "phone_number must be 13 digits and start with '234'"})

        data["user"] = user
        data["profile"] = profile
        return data


class MandateSerializer(serializers.ModelSerializer):
    """Serializer for reading mandate details (GET endpoints).
    
    Returns mandate status, identifiers, and timestamps.
    Does NOT return sensitive bank data.
    Optionally includes provider_response_code if available.
    """
    
    provider_response_code = serializers.SerializerMethodField()
    
    class Meta:
        model = Mandate
        fields = (
            "id",
            "status",
            "mandate_reference",
            "subscription_id",
            "request_ref",
            "activation_url",
            "created_at",
            "cancelled_at",
            "provider_response_code",
        )
        read_only_fields = fields
    
    def get_provider_response_code(self, obj):
        """Extract provider response code from last stored responses.
        
        Try cancel_response first (if available), then provider_response.
        """
        # Check cancel_response
        cancel_resp = getattr(obj, "cancel_response", None)
        if isinstance(cancel_resp, dict):
            code = cancel_resp.get("data", {}).get("provider_response_code")
            if code:
                return code
        
        # Fall back to provider_response
        provider_resp = getattr(obj, "provider_response", None)
        if isinstance(provider_resp, dict):
            code = provider_resp.get("data", {}).get("provider_response_code")
            if code:
                return code
        
        return None
