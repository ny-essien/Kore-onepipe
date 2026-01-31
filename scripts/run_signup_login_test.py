#!/usr/bin/env python
"""
Run signup and login flow using Django test client (no external server required).
"""
import os
import sys
import django
import json
from django.conf import settings

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


def run():
    client = APIClient()
    email = 'testuser+signup@example.com'
    name = 'Test User'
    password = 'Secret123!'

    # Ensure user doesn't already exist
    try:
        User.objects.filter(email=email).delete()
    except Exception:
        pass

    print('\n[STEP] Signing up')
    signup_resp = client.post('/api/auth/signup/', {
        'name': name,
        'email': email,
        'password': password,
        'confirm_password': password,
    }, format='json')

    print('Status:', signup_resp.status_code)
    try:
        print(json.dumps(signup_resp.json(), indent=2))
    except Exception:
        print(signup_resp.content)

    if signup_resp.status_code not in (200, 201):
        print('\nSignup failed, aborting login step')
        return 1

    print('\n[STEP] Logging in')
    login_resp = client.post('/api/auth/login/', {
        'email': email,
        'password': password,
    }, format='json')

    print('Status:', login_resp.status_code)
    try:
        data = login_resp.json()
        print(json.dumps(data, indent=2))
    except Exception:
        print(login_resp.content)
        return 1

    # If login returned tokens, show access token
    access = None
    if isinstance(data, dict) and data.get('tokens'):
        access = data['tokens'].get('access')
    elif isinstance(data, dict) and data.get('access'):
        access = data.get('access')

    if access:
        print('\n✅ Obtained access token (first 40 chars):', access[:40])
        return 0
    else:
        print('\n⚠️ No access token returned')
        return 1


if __name__ == '__main__':
    sys.exit(run())
