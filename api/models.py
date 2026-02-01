from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Profile(models.Model):
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
    ]

    # Relationships
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Personal Info
    first_name = models.CharField(max_length=255, blank=True)
    surname = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)

    # Bank Info (encrypted at rest)
    bank_name = models.CharField(max_length=255, blank=True)
    bank_code = models.CharField(max_length=10, blank=True)  # CBN bank code
    account_number_encrypted = models.TextField(blank=True)  # Encrypted account number
    bvn_encrypted = models.TextField(blank=True)  # Encrypted BVN

    # Draft Data (unverified personal + bank data pending lookup)
    draft_payload = models.JSONField(default=dict, blank=True)

    # Flags
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        name = f"{self.first_name} {self.surname}".strip() or "Unknown"
        return f"Profile: {name} ({self.user.email})"


class ProfileVerificationAttempt(models.Model):
    """Audit trail for bank verification attempts"""
    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("error", "Error"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_attempts")
    request_ref = models.CharField(max_length=255)  # OnePipe request reference
    request_type = models.CharField(max_length=50)  # e.g. "lookup accounts min"
    payload_sent = models.JSONField()  # Redacted payload (no plaintext)
    response = models.JSONField()  # OnePipe response
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"VerificationAttempt({self.user.email}, {self.status}, {self.created_at})"


class WebhookEvent(models.Model):
    """Store raw webhook events for audit and debugging"""
    PROVIDER_CHOICES = [
        ("onepipe", "OnePipe"),
    ]

    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    payload = models.JSONField()  # Raw webhook payload
    verification_attempt = models.ForeignKey(
        ProfileVerificationAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events"
    )
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)  # Error message if processing failed
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"WebhookEvent({self.provider}, {self.processed}, {self.received_at})"


class RulesEngine(models.Model):
    """
    Stores debit rules and limits for a user.
    
    Defines:
    - Maximum debit amounts (monthly, per transaction)
    - Frequency-based spending limits
    - Fund allocation percentages
    - Failure handling strategy
    - Active date range
    
    Constraint: Only one active RulesEngine per user at any time.
    """
    
    FREQUENCY_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("CUSTOM", "Custom"),
    ]
    
    FAILURE_ACTION_CHOICES = [
        ("RETRY", "Retry Transaction"),
        ("SKIP", "Skip Transaction"),
        ("NOTIFY", "Notify User"),
    ]
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rules")
    
    # Debit Limits
    monthly_max_debit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Maximum amount that can be debited in a month"
    )
    single_max_debit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Maximum amount allowed for a single transaction"
    )
    
    # Frequency-based Limits
    frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default="MONTHLY",
        help_text="Frequency of the spending limit"
    )
    amount_per_frequency = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Maximum amount allowed per frequency period"
    )
    
    # Fund Allocation
    allocations = models.JSONField(
        default=list,
        blank=True,
        help_text="List of fund allocation rules. Example: [{'bucket': 'SAVINGS', 'percentage': 50}, {'bucket': 'SPENDING', 'percentage': 50}]"
    )
    
    # Failure Handling
    failure_action = models.CharField(
        max_length=10,
        choices=FAILURE_ACTION_CHOICES,
        default="NOTIFY",
        help_text="Action to take when transaction fails verification"
    )
    
    # Timeline
    start_date = models.DateField(
        help_text="Date when this rule becomes active"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this rule expires (null = indefinite)"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this rule is currently active"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Rules Engine"
        verbose_name_plural = "Rules Engines"
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"RulesEngine({self.user.email}, {status})"
    
    def clean(self):
        """
        Validate model constraints:
        - Only one active rule per user at any time
        - start_date should not be after end_date
        """
        # Check for only one active rule per user
        if self.is_active:
            active_rules = RulesEngine.objects.filter(
                user=self.user,
                is_active=True
            ).exclude(pk=self.pk)  # Exclude current instance during updates
            
            if active_rules.exists():
                raise ValidationError(
                    f"User {self.user.email} already has an active rule. "
                    "Please deactivate the existing rule before creating a new one."
                )
        
        # Check date logic
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("start_date cannot be after end_date")
    
    def save(self, *args, **kwargs):
        """Run validation before saving"""
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_active_for_user(cls, user):
        """Return the most recently created active RulesEngine for a user, or None."""
        return cls.objects.filter(user=user, is_active=True).order_by("-created_at").first()


class Mandate(models.Model):
    """
    Stores OnePipe "create mandate" results for recurring debit instructions.
    
    A mandate is the authorization to debit a user's account for recurring payments.
    Linked to a RulesEngine to track which rules triggered mandate creation.
    """
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("ACTIVE", "Active"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mandates",
        help_text="User who owns this mandate"
    )
    rules_engine = models.ForeignKey(
        RulesEngine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mandates",
        help_text="RulesEngine that triggered this mandate creation"
    )
    
    # Status
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
        help_text="Current status of the mandate"
    )
    
    # References
    request_ref = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique reference for this mandate request"
    )
    transaction_ref = models.CharField(
        max_length=64,
        blank=True,
        help_text="Transaction reference from provider (if applicable)"
    )
    payment_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Provider payment id used for mandate cancellation",
    )
    mandate_reference = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Provider mandate reference identifier",
    )
    subscription_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Provider subscription id if available",
    )
    
    # Provider Response
    activation_url = models.URLField(
        blank=True,
        help_text="URL to activate/authorize the mandate (if provider returns one)"
    )
    provider_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw response from payment provider"
    )

    # Cancel audit
    cancel_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw provider response for cancel attempts"
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the mandate was cancelled by the user/provider"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mandate"
        verbose_name_plural = "Mandates"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created_at"]),
        ]
    
    def __str__(self):
        return f"Mandate({self.user.email}, {self.status}, {self.request_ref})"


class Transaction(models.Model):
    """Model for transaction records (debits/credits)"""
    TRANSACTION_TYPE_CHOICES = [
        ("debit", "Debit"),
        ("credit", "Credit"),
    ]
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    
    BUCKET_CHOICES = [
        ("savings", "Savings"),
        ("investment", "Investment"),
        ("emergency", "Emergency"),
        ("custom", "Custom"),
    ]
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    
    # Transaction Details
    reference = models.CharField(max_length=50, unique=True, db_index=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    
    # Bucket Information
    bucket = models.CharField(max_length=20, choices=BUCKET_CHOICES, null=True, blank=True)
    custom_bucket_name = models.CharField(max_length=255, blank=True)
    
    # Transaction Info
    description = models.CharField(max_length=500, blank=True)
    narration = models.CharField(max_length=500, blank=True)
    
    # Provider Reference (for external integrations)
    request_ref = models.CharField(max_length=100, blank=True, db_index=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reference"]),
        ]
    
    def __str__(self):
        return f"Transaction({self.reference}, {self.amount}, {self.status})"
    
    @classmethod
    def generate_reference(cls):
        """Generate a unique transaction reference"""
        import uuid
        return f"TXN-{uuid.uuid4().hex[:12].upper()}"
