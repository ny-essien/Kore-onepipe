# API Routes Reference

This document lists all routes defined in `api/urls.py`, their HTTP method(s), authentication requirement, and a short description with notes and example payloads where useful.

- **GET** `/api/services/`
  - Auth: None (public)
  - Description: Returns a static list of supported financial services. Used by the frontend for rules engine and service selection during mandate setup.
  - Response: 
    ```json
    {
      "services": [
        { "key": "SAVINGS", "label": "Savings" },
        { "key": "INVESTMENT", "label": "Investment" },
        { "key": "TAX", "label": "Tax" },
        { "key": "LOANS", "label": "Loans" },
        { "key": "BILLS", "label": "Bills" }
      ]
    }
    ```

- **GET** `/api/banks/`
  - Auth: None (public)
  - Description: Returns a simplified list of banks from OnePipe. Uses cache key `onepipe:get_banks` (TTL 3600s). If provider is down and cache exists, returns cached banks with `"stale": true`.
  - Response: JSON array of objects: `[ {"name": "Access Bank", "code": "044"}, ... ]` or when stale: `{ "banks": [...], "stale": true }`

- **POST** `/api/auth/signup/`
  - Auth: None
  - Description: Register a new user. Creates a `User` and a `Profile`. Returns user data and JWT tokens.
  - Example payload:
    ```json
    { "name": "Alice", "email": "alice@example.com", "password": "secret", "confirm_password": "secret" }
    ```
  - Success: 201 Created with `user` and `tokens` (access + refresh)

- **POST** `/api/auth/login/`
  - Auth: None
  - Description: Sign in an existing user. Returns user data and JWT tokens.
  - Example payload:
    ```json
    { "email": "alice@example.com", "password": "secret" }
    ```
  - Success: 200 OK with `user` and `tokens`

- **GET** `/api/auth/me/`
  - Auth: Required (Bearer access token)
  - Description: Returns basic authenticated user info and profile `is_completed` flag.
  - Response: `{ "id": 1, "name": "Alice", "email": "alice@example.com", "profile": { "is_completed": false } }`

- **GET** `/api/profile/me/`
  - Auth: Required
  - Description: Read-only view of profile details (first_name, surname, phone number, DOB, gender, bank_name, bank_code, is_completed)

- **PATCH** `/api/profile/personal/`
  - Auth: Required
  - Description: Update personal fields (first_name, surname, phone_number, date_of_birth, gender). Saves data to `profile.draft_payload.personal` for review before submission.
  - Note: Validations applied (phone format, past DOB).

- **PATCH** `/api/profile/bank/`
  - Auth: Required
  - Description: Update bank information and encrypt sensitive fields. Saved to `profile.draft_payload.bank` (not committed to final profile until verification succeeds).
  - Input fields: `account_number` (10 digits), `bank_name`, `bank_code`, `bvn` (11 digits).
  - Note: `BankInfoSerializer` encrypts `account_number` and `bvn` using `api/encryption.py` (Fernet) before storing in the draft payload or `profile` fields.

- **POST** `/api/profile/submit/`
  - Auth: Required
  - Description: Submit the draft personal + bank data for verification (OnePipe "lookup accounts min"). The view builds a OnePipe payload using `build_lookup_accounts_min_payload()` and calls `OnePipeClient.transact()`.
  - Behavior:
    - Requires both `draft_payload.personal` and `draft_payload.bank` to exist.
    - On successful verification, copies draft data into final `profile` fields, marks `profile.is_completed = True`, clears draft, and stores a `ProfileVerificationAttempt` record.
    - On failure, logs a `ProfileVerificationAttempt` with status `failed` and returns 400.
  - Notes: OnePipe auth uses header `Authorization: Bearer {ONEPIPE_API_KEY}` and `Signature: MD5(request_ref;CLIENT_SECRET)`.

- **POST** `/api/webhooks/onepipe/`
  - Auth: None (public webhook)
  - Description: Receives webhook events from OnePipe. Stores raw payload as `WebhookEvent` and attempts to correlate with a `ProfileVerificationAttempt` by `request_ref`. Always returns 200 OK to avoid retries.

- **POST** `/api/token/` and **POST** `/api/token/refresh/`
  - Auth: None
  - Description: Standard JWT token obtain/refresh endpoints from `djangorestframework-simplejwt` (available if needed). These are provided alongside the custom auth views.

---

## Rules Engine Endpoints

- **POST** `/api/rules-engine/`
  - Auth: Required
  - Description: Create debit rules for the authenticated user. Only one active rule allowed per user.
  - Example payload:
    ```json
    {
      "monthly_max_debit": 50000.00,
      "single_max_debit": 10000.00,
      "frequency": "MONTHLY",
      "amount_per_frequency": 50000.00,
      "allocations": [
        {"bucket": "SAVINGS", "percentage": 50},
        {"bucket": "SPENDING", "percentage": 50}
      ],
      "failure_action": "NOTIFY",
      "start_date": "2026-02-01",
      "end_date": null
    }
    ```
  - Success: 201 Created with rule details and `"ready_for_mandate": true`
  - Notes: Auto-deactivates any previous active rules for the user.

- **GET** `/api/rules-engine/me/`
  - Auth: Required
  - Description: Fetch the currently active RulesEngine for the authenticated user.
  - Success: 200 OK with rule details
  - Not Found: 404 with message `"No rules engine configured yet."`

- **PATCH** `/api/rules-engine/me/`
  - Auth: Required
  - Description: Partially update the active RulesEngine (supports all numeric, frequency, allocations, failure_action, and date fields).
  - Success: 200 OK with updated rule
  - Not Found: 404 if no active rule exists

- **POST** `/api/rules-engine/me/disable/`
  - Auth: Required
  - Description: Disable (soft-delete) the active RulesEngine by setting `is_active = False`.
  - Success: 200 OK with message `"Rules engine disabled"`
  - Not Found: 404 if no active rule exists

---

## Mandate Endpoints

- **POST** `/api/mandates/create/`
  - Auth: Required
  - Description: Create a mandate via OnePipe PayWithAccount integration. Requires a completed profile and active RulesEngine.
  - Prerequisites:
    - `profile.is_completed = True`
    - Active RulesEngine exists
    - Profile has: first_name, surname, phone_number (format: 13 digits starting with "234"), bank_code, account_number_encrypted, bvn_encrypted
  - Example payload:
    ```json
    {
      "customer_consent": "<optional base64 string>"
    }
    ```
  - Success: 201 Created
    ```json
    {
      "id": 42,
      "status": "PENDING",
      "request_ref": "abc123def456",
      "activation_url": "https://provider.com/activate"
    }
    ```
  - Stores mandate data including:
    - Provider response (mandate_reference, subscription_id if available)
    - Status: ACTIVE (if provider status="ACTIVE") or PENDING
  - Failure: 400 or 502 with provider error details

- **GET** `/api/mandates/me/`
  - Auth: Required
  - Description: Fetch the latest mandate for the authenticated user.
  - Success: 200 OK
    ```json
    {
      "id": 42,
      "status": "ACTIVE",
      "mandate_reference": "mandate-ref-123",
      "subscription_id": 789,
      "request_ref": "abc123def456",
      "activation_url": "https://example.com/activate",
      "created_at": "2026-02-01T10:30:00Z",
      "cancelled_at": null,
      "provider_response_code": "00"
    }
    ```
  - Not Found: 404 with message `"No mandate found for this user."`

- **POST** `/api/mandates/cancel/`
  - Auth: Required
  - Description: Cancel an active mandate via OnePipe. Requires user's latest ACTIVE mandate to exist with `mandate_reference` set.
  - Prerequisites:
    - Latest ACTIVE mandate exists
    - `mandate.mandate_reference` is set
    - Profile has: first_name, surname, phone_number (13 digits starting with "234")
  - Example payload:
    ```json
    {}
    ```
  - Success: 200 OK
    ```json
    {
      "message": "Mandate cancelled",
      "mandate_status": "CANCELLED"
    }
    ```
  - Success condition: `response["status"] == "Successful"` AND `response["data"]["provider_response_code"] == "00"`
  - On success:
    - Mandate status set to CANCELLED
    - cancelled_at timestamp recorded
    - cancel_response stored for audit
  - On failure: 400 with provider error (mandate status remains ACTIVE, cancel_response stored)
  - Not Found: 404 if no active mandate exists
  - Bad Request: 400 if mandate_reference missing

---

Notes and implementation details

- URL module: `api/urls.py` maps the above routes to views in `api/views.py`.
- OnePipe integration:
  - `api/onepipe_client.py` provides `OnePipeClient`, `build_get_banks_payload()`, `build_lookup_accounts_min_payload()`, `build_create_mandate_payload()`, and `build_cancel_mandate_payload()`.
  - `build_lookup_accounts_min_payload()` encrypts `account_number;bank_code` using Triple DES (3DES-CBC) per PayWithAccount spec; `auth.secure` is the encrypted base64 payload.
  - `build_create_mandate_payload()` constructs the mandate creation request with triple-DES encrypted auth fields.
  - `build_cancel_mandate_payload()` constructs the cancel mandate request using the stored `mandate_reference`.
  - `OnePipeClient.transact()` signs all requests with `Signature: MD5(request_ref;CLIENT_SECRET)` (UTF-8, lowercase hex).
- Local encryption at rest uses `api/encryption.py` (Fernet) for storing account numbers and BVN in the database. This is distinct from the OnePipe encryption scheme.
- Caching:
  - `GET /api/banks/` uses Django cache key `onepipe:get_banks` with TTL 3600s.
- Mandate lifecycle:
  - PENDING: Created, awaiting provider activation
  - ACTIVE: Provider confirmed activation
  - FAILED: Creation failed
  - CANCELLED: User cancelled successfully

If you want, I can:
- Generate example curl commands for each route.
- Add an OpenAPI snippet or Postman collection generated from these endpoints.

