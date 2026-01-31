from django.db import models
from django.contrib.auth.models import User


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
