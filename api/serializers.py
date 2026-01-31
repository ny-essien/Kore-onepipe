from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class UserSerializer(serializers.ModelSerializer):
    """Serializer for returning user data"""
    name = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "name", "email")
        read_only_fields = ("id",)


class RegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("name", "email", "password", "confirm_password")

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
            first_name=validated_data["name"],
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

