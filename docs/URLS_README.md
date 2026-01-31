# API Routes Reference

This document lists all routes defined in `api/urls.py`, their HTTP method(s), authentication requirement, and a short description with notes and example payloads where useful.

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

Notes and implementation details

- URL module: `api/urls.py` maps the above routes to views in `api/views.py`.
- OnePipe integration:
  - `api/onepipe_client.py` provides `OnePipeClient`, `build_get_banks_payload()`, and `build_lookup_accounts_min_payload()`.
  - `build_lookup_accounts_min_payload()` encrypts `account_number;bank_code` using Triple DES (3DES-CBC) per PayWithAccount spec; `auth.secure` is the encrypted base64 payload.
- Local encryption at rest uses `api/encryption.py` (Fernet) for storing account numbers and BVN in the database. This is distinct from the OnePipe encryption scheme.
- Caching:
  - `GET /api/banks/` uses Django cache key `onepipe:get_banks` with TTL 3600s.

If you want, I can:
- Generate example curl commands for each route.
- Add an OpenAPI snippet or Postman collection generated from these endpoints.

