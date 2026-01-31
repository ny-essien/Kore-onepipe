import os
import django
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so Django can import settings
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure settings are picked up from project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kore.settings')
django.setup()

from api.onepipe_client import OnePipeClient, build_lookup_accounts_min_payload

# Test data (from user)
customer_ref = 'live-test-nsikan-essien'
account_number = '0253700042'
bank_code = '058'
first_name = 'Nsikan'
last_name = 'Essien'
email = 'nsikan4001@gmail.com'
mobile_no = '2348147246183'

# Build payload
payload = build_lookup_accounts_min_payload(
    customer_ref=customer_ref,
    account_number=account_number,
    bank_code=bank_code,
    bvn=None,
    meta=None,
    first_name=first_name,
    last_name=last_name,
    mobile_no=mobile_no,
)

print('Sending payload:')
print(json.dumps(payload, indent=2))

client = OnePipeClient()
try:
    result = client.transact(payload)
    print('\nResponse:')
    print(json.dumps(result, indent=2, default=str))
except Exception as e:
    print('\nError:')
    print(str(e))
