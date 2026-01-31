#!/usr/bin/env python
import os
import sys
import django
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from rest_framework.test import APIClient

client = APIClient()
resp = client.get('/api/')
print(json.dumps(resp.json(), indent=2))
