import os
from pathlib import Path

print('ONEPIPE_API_KEY =', repr(os.getenv('ONEPIPE_API_KEY')))
print('ONEPIPE_CLIENT_SECRET =', repr(os.getenv('ONEPIPE_CLIENT_SECRET')))
print('CWD =', Path.cwd())

try:
    import django
    print('Django available')
except Exception as e:
    print('Django import error:', e)

try:
    from api.onepipe_client import OnePipeClient
    print('OnePipeClient import succeeded')
except Exception as e:
    print('OnePipeClient import error:', e)
