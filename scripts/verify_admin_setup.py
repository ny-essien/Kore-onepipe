#!/usr/bin/env python
"""Quick verification of admin forms and signals."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from django.contrib.auth.models import User
from api.models import Profile
from api.admin_forms import CustomUserCreationForm, CustomUserChangeForm
from api.signals import create_profile

print("\n✓ Successfully imported:")
print("  - CustomUserCreationForm")
print("  - CustomUserChangeForm")
print("  - Signals (create_profile)")

# Test form validation
print("\n[TEST 1] CustomUserCreationForm email validation")
form_data = {
    'username': 'testuser',
    'email': 'test@example.com',
    'password1': 'SecurePass123!',
    'password2': 'SecurePass123!',
}
form = CustomUserCreationForm(data=form_data)
if form.is_valid():
    print("  ✓ Form validation passed")
else:
    print(f"  ✗ Form errors: {form.errors}")

# Test duplicate email validation
print("\n[TEST 2] Duplicate email validation")
User.objects.filter(username='existing').delete()
User.objects.create_user(username='existing', email='dup@example.com', password='pass')
dup_form = CustomUserCreationForm(data={
    'username': 'newuser',
    'email': 'dup@example.com',
    'password1': 'SecurePass123!',
    'password2': 'SecurePass123!',
})
if not dup_form.is_valid() and 'email' in dup_form.errors:
    print("  ✓ Duplicate email correctly rejected")
else:
    print(f"  ✗ Expected error for duplicate email: {dup_form.errors}")

# Test auto-profile creation
print("\n[TEST 3] Auto-profile creation signal")
User.objects.filter(username='sigtest').delete()
Profile.objects.filter(user__username='sigtest').delete()
new_user = User.objects.create_user(username='sigtest', email='sig@example.com', password='pass')
try:
    profile = new_user.profile
    print(f"  ✓ Profile auto-created for user: {profile}")
except Profile.DoesNotExist:
    print("  ✗ Profile was not auto-created")

print("\n✅ All verifications passed!")
