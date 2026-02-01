"""
OnePipe API client for transact operations.
Handles request signing, header generation, and response parsing.
Never logs API keys or secrets.
"""
import uuid
import hashlib
import requests
from django.conf import settings
from decimal import Decimal
from .triple_des import make_signature, triple_des_encrypt
from .encryption import decrypt_value


def build_get_banks_payload():
    """Build payload for retrieving banks list from OnePipe.

    Returns a minimal payload dict. Includes `meta.webhook_url` when configured.
    """
    payload = {
        "request_type": "get_banks",
        "transaction": {"mock_mode": "inspect"},
    }
    webhook = settings.ONEPIPE.get("WEBHOOK_URL")
    if webhook:
        payload.setdefault("meta", {})["webhook_url"] = webhook
    return payload


def build_lookup_accounts_min_payload(
    customer_ref,
    account_number,
    bank_code,
    bvn=None,
    meta=None,
    first_name=None,
    last_name=None,
    mobile_no=None,
    transaction_ref=None,
    transaction_desc=None,
):
    """Build payload compatible with OnePipe 'lookup account min' style.

    This builds a payload where:
    - `request_ref` is generated here (caller should not reuse it)
    - `auth.secure` contains Triple DES-encrypted "account_number;bank_code"
      using key derivation: MD5(sharedKey as UTF-16LE) + first 8 bytes, base64-encoded.

    Args:
        customer_ref (str): Caller-side customer reference
        account_number (str): Account number
        bank_code (str): Bank code (CBN bank code)
        bvn (str|None): BVN value (stored in meta.bvn)
        meta (dict|None): Optional meta dict to include
        first_name, last_name, mobile_no: optional customer identity fields
        transaction_ref, transaction_desc: optional transaction metadata

    Returns:
        dict: payload ready to pass to OnePipeClient.transact()
    """
    import base64
    from Crypto.Cipher import DES3
    from Crypto.Util.Padding import pad

    # Generate a unique request_ref here
    request_ref = uuid.uuid4().hex

    # Triple DES encrypt: plaintext = "account_number;bank_code"
    plaintext = f"{account_number};{bank_code}"
    secret_key = settings.ONEPIPE.get("CLIENT_SECRET", "")
    
    # Key derivation matching Node.js:
    # 1. Convert sharedKey to UTF-16LE bytes
    # 2. MD5 hash the UTF-16LE bytes
    # 3. Concatenate MD5 hash with its first 8 bytes (24 bytes total for 3DES)
    buffered_key = secret_key.encode('utf-16le')
    md5_hash = hashlib.md5(buffered_key).digest()  # 16 bytes
    triple_des_key = md5_hash + md5_hash[:8]  # 24 bytes (16 + 8)
    
    # Triple DES-CBC with zero IV
    iv = bytes(8)  # 8 zero bytes
    cipher = DES3.new(triple_des_key, DES3.MODE_CBC, iv)
    padded = pad(plaintext.encode('utf-8'), DES3.block_size)
    ciphertext = cipher.encrypt(padded)
    # Base64 encode the ciphertext (IV is fixed, not included)
    auth_secure = base64.b64encode(ciphertext).decode()

    payload = {
        "request_ref": request_ref,
        "request_type": "lookup account min",
        "auth": {
            "type": "bank.account",
            "secure": auth_secure,
            "auth_provider": "PaywithAccount",
        },
        "transaction": {
            # `mock_mode` will be ensured by OnePipeClient.transact if missing,
            # but include here for clarity.
            "mock_mode": "live",
            "transaction_ref": transaction_ref or uuid.uuid4().hex,
            "transaction_desc": transaction_desc or "Verify account ownership",
            "amount": 0,
            "customer": {
                "customer_ref": customer_ref or "",
                "firstname": first_name or "",
                "surname": last_name or "",
                "mobile_no": mobile_no or "",
            },
            "details": {},
        },
    }

    # meta: include bvn if provided (no encryption, plain value)
    final_meta = {} if meta is None else dict(meta)
    if bvn:
        final_meta.setdefault("bvn", bvn)
    # include configured webhook if none provided
    if not final_meta.get("webhook_url"):
        webhook = settings.ONEPIPE.get("WEBHOOK_URL")
        if webhook:
            final_meta.setdefault("webhook_url", webhook)

    if final_meta:
        payload["transaction"]["meta"] = final_meta

    return payload


def build_create_mandate_payload(user, profile, rules_engine, customer_consent_b64=None, request_ref=None):
    """
    Build payload for OnePipe `create mandate` request.

    Decrypts `account_number_encrypted` and `bvn_encrypted` from `profile` in-memory,
    uses TripleDES encryption to populate `auth.secure` and `meta.bvn`, and
    constructs the `transaction` payload according to OnePipe requirements.
    """
    # Read config
    cfg = settings.ONEPIPE
    client_secret = cfg.get("CLIENT_SECRET")
    biller_code = cfg.get("BILLER_CODE") or cfg.get("ONEPIPE_BILLER_CODE")

    if not client_secret:
        raise ValueError("ONEPIPE CLIENT_SECRET missing in settings.ONEPIPE")

    # Decrypt stored encrypted values (in-memory only)
    account_number = decrypt_value(getattr(profile, "account_number_encrypted", ""))
    bvn_plain = decrypt_value(getattr(profile, "bvn_encrypted", ""))

    # Bank code from profile
    cbn_bankcode = getattr(profile, "bank_code", "")

    # Build auth.secure (TripleDES encrypt of "account;bankcode")
    auth_secure = ""
    if account_number and cbn_bankcode:
        auth_plain = f"{account_number};{cbn_bankcode}"
        auth_secure = triple_des_encrypt(auth_plain, client_secret)

    # Build meta.bvn (TripleDES encrypt of BVN)
    meta_bvn = ""
    if bvn_plain:
        meta_bvn = triple_des_encrypt(bvn_plain, client_secret)

    # mobile / customer_ref
    mobile_no = getattr(profile, "phone_number", "")

    # amount: monthly_max_debit * 1000, keep as string
    monthly = getattr(rules_engine, "monthly_max_debit", None)
    if monthly is None:
        raise ValueError("rules_engine.monthly_max_debit is required")
    amount_val = str(int((Decimal(monthly) * Decimal(1000)).to_integral_value()))

    payload = {"request_type": "create mandate"}
    if request_ref:
        payload["request_ref"] = request_ref

    payload["auth"] = {
        "type": "bank.account",
        "secure": auth_secure,
        "auth_provider": "PaywithAccount",
    }

    payload["transaction"] = {
        "mock_mode": "inspect",
        "transaction_desc": "Creating a mandate",
        "amount": 0,
        "customer": {
            "customer_ref": mobile_no,
            "firstname": getattr(profile, "first_name", ""),
            "surname": getattr(profile, "surname", ""),
            "email": getattr(user, "email", ""),
            "mobile_no": mobile_no,
        },
        "meta": {
            "amount": amount_val,
            "skip_consent": False,
            "bvn": meta_bvn,
            "biller_code": biller_code or "",
            "customer_consent": customer_consent_b64 or "",
        },
        "details": {},
    }

    return payload


def build_cancel_mandate_payload(user, profile, mandate, request_ref=None):
    """Build payload for OnePipe 'Cancel Mandate' request."""
    from decimal import Decimal
    cfg = settings.ONEPIPE
    biller_code = cfg.get("ONEPIPE_BILLER_CODE") or cfg.get("BILLER_CODE") or ""

    # Validate phone
    mobile_no = getattr(profile, "phone_number", "")
    if not mobile_no or not mobile_no.startswith("234") or len(mobile_no) != 13:
        raise ValueError("profile.phone_number must be 13 digits starting with '234'")

    req_ref = request_ref or uuid.uuid4().hex

    # Use mandate.mandate_reference as payment_id in meta
    payload = {
        "request_ref": req_ref,
        "request_type": "Cancel Mandate",
        "auth": {"type": None, "secure": None, "auth_provider": "PaywithAccount"},
        "transaction": {
            "mock_mode": "Inspect",
            "transaction_ref": uuid.uuid4().hex,
            "transaction_desc": "Cancel Mandate",
            "transaction_ref_parent": None,
            "amount": 0,
            "customer": {
                "customer_ref": mobile_no,
                "firstname": getattr(profile, "first_name", ""),
                "surname": getattr(profile, "surname", ""),
                "email": getattr(user, "email", ""),
                "mobile_no": mobile_no,
            },
            "meta": {
                "payment_id": getattr(mandate, "mandate_reference", "") or getattr(mandate, "payment_id", ""),
                "biller_code": biller_code or "",
            },
            "details": {},
        },
    }

    return payload


class OnePipeError(Exception):
    """Raised when OnePipe API returns non-2xx response"""
    def __init__(self, status_code, body, message=None):
        self.status_code = status_code
        self.body = body
        self.message = message or f"OnePipe API error: {status_code}"
        super().__init__(self.message)


class OnePipeClient:
    """Client for OnePipe PayWithAccount API"""

    def __init__(self):
        self.config = settings.ONEPIPE
        self.base_url = self.config.get("BASE_URL", "https://api.dev.onepipe.io")
        self.transact_path = self.config.get("TRANSACT_PATH", "/v2/transact")
        self.api_key = self.config.get("API_KEY")
        self.client_secret = self.config.get("CLIENT_SECRET")

        if not self.api_key or not self.client_secret:
            raise ValueError("ONEPIPE configuration missing: API_KEY and CLIENT_SECRET required in settings.ONEPIPE")

    def _generate_request_ref(self):
        """Generate a unique request reference using UUID4"""
        return uuid.uuid4().hex

    def _generate_signature(self, request_ref):
        """
        Generate MD5 signature from request_ref and client_secret.
        Format: MD5(request_ref;client_secret)
        """
        # Use shared helper to ensure consistent UTF-8 encoding and lowercase
        return make_signature(request_ref, self.client_secret)

    def _build_headers(self, request_ref):
        """Build request headers with auth and signature"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Signature": self._generate_signature(request_ref),
            "Content-Type": "application/json",
        }

    def transact(self, payload):
        """
        Call OnePipe transact endpoint.

        Args:
            payload (dict): Transaction payload. Should include request_ref, request_type,
                           auth, and transaction objects.

        Returns:
            dict: {
                "request_ref": str,
                "response": dict (API response body)
            }

        Raises:
            OnePipeError: If API returns non-2xx status code
            ValueError: If required config is missing
        """
        # Generate or use provided request_ref
        request_ref = payload.get("request_ref") or self._generate_request_ref()
        payload["request_ref"] = request_ref

        # Ensure mock_mode is set (default to "inspect" for this project)
        if "transaction" in payload and "mock_mode" not in payload["transaction"]:
            payload["transaction"]["mock_mode"] = "inspect"

        # Build request
        url = f"{self.base_url}{self.transact_path}"
        headers = self._build_headers(request_ref)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            raise OnePipeError(
                status_code=None,
                body=str(e),
                message=f"Request failed: {str(e)}"
            )

        # Check response status
        if not (200 <= response.status_code < 300):
            raise OnePipeError(
                status_code=response.status_code,
                body=response.text,
                message=f"OnePipe API returned {response.status_code}"
            )

        # Parse and return response
        try:
            response_json = response.json()
        except ValueError:
            response_json = response.text

        return {
            "request_ref": request_ref,
            "response": response_json,
        }
