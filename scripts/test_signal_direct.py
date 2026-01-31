#!/usr/bin/env python
"""
Simple test to verify signal works when creating a user directly.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from django.contrib.auth import get_user_model
from api.models import Profile

User = get_user_model()

print("\n" + "="*60)
print("Testing auto-profile signal...")
print("="*60)

email = "test.signal.direct@example.com"

# Clean up
User.objects.filter(email=email).delete()

print(f"\nCreating user with email: {email}")
user = User.objects.create_user(
    username=email,
    email=email,
    first_name="Test",
    password="TestPassword123!"
)
print(f"✓ User created: {user.username} (ID: {user.id})")

# Check profile
profile_count = Profile.objects.filter(user=user).count()
print(f"\nProfile count for this user: {profile_count}")

if profile_count > 0:
    profile = Profile.objects.get(user=user)
    print(f"✓ SUCCESS: Profile auto-created!")
    print(f"  Profile ID: {profile.id}")
    print(f"  Profile User: {profile.user.username}")
else:
    print(f"✗ FAILED: Profile NOT auto-created")
    print(f"  Expected 1 profile, found {profile_count}")

print("\n" + "="*60)
