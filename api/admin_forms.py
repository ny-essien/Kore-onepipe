"""
Custom forms for Django admin User creation and modification.

Extends Django's default forms to:
1. Add email field (required) to user creation form
2. Validate email uniqueness (case-insensitive)
3. Present "Full name" field instead of separate first/last name
4. Ensure consistency between API signup and admin user creation

Why custom forms?
- Django's default UserCreationForm does NOT include email, only username
- We need email validation and consistency with our API
- We use full_name (stored in first_name) for better UX
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    """
    Custom form for creating users in Django admin.
    
    Adds:
    - Email field (required, with uniqueness validation)
    - Full name field (replaces separate first_name/last_name fields)
    - Username is auto-generated from email (hidden from user)
    
    Removes:
    - Username field (no longer required from user, auto-generated)
    """
    
    email = forms.EmailField(
        required=True,
        help_text="Required. Must be a valid email address.",
        label="Email"
    )
    
    full_name = forms.CharField(
        max_length=150,
        required=True,
        help_text="The user's full name",
        label="Full name"
    )
    
    class Meta:
        model = User
        fields = ("email", "full_name", "password1", "password2")
    
    def clean_email(self):
        """Validate that email is unique (case-insensitive)"""
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email
    
    def save(self, commit=True):
        """Save user with email as username (auto-generated), and full_name"""
        user = super().save(commit=False)
        # Auto-generate username from email
        email = self.cleaned_data.get("email")
        user.username = email
        user.email = email
        user.first_name = self.cleaned_data.get("full_name")
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """
    Custom form for modifying users in Django admin.
    
    Adds:
    - Email field with uniqueness validation (excluding current user)
    - Full name field instead of separate first_name/last_name
    
    Removes:
    - Username field (auto-generated from email, cannot be changed)
    """
    
    email = forms.EmailField(
        required=True,
        help_text="The user's email address",
        label="Email"
    )
    
    full_name = forms.CharField(
        max_length=150,
        required=False,
        help_text="The user's full name",
        label="Full name"
    )
    
    class Meta:
        model = User
        fields = ("email", "full_name", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")
    
    def clean_email(self):
        """Validate that email is unique (case-insensitive), excluding current user"""
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this email already exists.")
        return email
    
    def save(self, commit=True):
        """Save user with email and full_name set"""
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email")
        full_name = self.cleaned_data.get("full_name")
        if full_name:
            user.first_name = full_name
        if commit:
            user.save()
        return user
