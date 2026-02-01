# KORE API Documentation

Version: 1.0
Date: 2026-02-01

This document describes the HTTP APIs provided by the KORE backend (Django + Django REST Framework) for frontend engineers and integration partners. It documents only the endpoints implemented in the codebase and explains request/response shapes, validation rules, and integration notes for the OnePipe PayWithAccount flows.

---

**Table of contents**

1. Project Overview
2. Authentication & Authorization
3. User & Profile APIs
4. Services API
5. Rules Engine APIs
6. Mandate APIs (PayWithAccount Integration)
7. Webhooks
8. Common Response Formats
9. Environment & Configuration (High Level)
10. Notes & Constraints

---

## 1) Project Overview

KORE is a backend service that verifies user bank accounts via OnePipe PayWithAccount, allows users to configure debit rules (Rules Engine), and creates/manages recurring debit mandates.

High-level flow:
- Authentication → Profile Completion → Rules Engine → Mandate Creation → Mandate Management

Typical integration steps for a frontend:
1. Sign up / log in to obtain JWT access token.
2. Complete profile (personal + bank info) and submit for verification.
3. Create a Rules Engine (debit rules) for the user.
4. Create a Mandate which tokenizes the account with OnePipe.
5. Retrieve or cancel the mandate as needed.

---

## 2) Authentication & Authorization

Authentication method: JWT tokens (djangorestframework-simplejwt). Use the `access` token in the `Authorization: Bearer <access_token>` header for protected endpoints.

### Signup
- Method: POST
- URL: `/api/auth/signup/`
- Auth: No
- Request headers: `Content-Type: application/json`
- Request payload example:

```json
{
  "full_name": "Alice Example",
  "email": "alice@example.com",
  "password": "secret123",
  "confirm_password": "secret123"
}
```

- Success response (201):

```json
{
  "user": { "id": 1, "name": "Alice Example", "email": "alice@example.com" },
  "tokens": { "access": "<jwt>", "refresh": "<jwt_refresh>" }
}
```

- Errors (400): validation messages, e.g., email already registered or password mismatch.

### Login
- Method: POST
- URL: `/api/auth/login/`
- Auth: No
- Request payload example:

```json
{ "email": "alice@example.com", "password": "secret123" }
```

- Success response (200):

```json
{
  "user": { "id": 1, "name": "Alice Example", "email": "alice@example.com" },
  "tokens": { "access": "<jwt>", "refresh": "<jwt_refresh>" }
}
```

- Errors (400): `Invalid credentials.`

### Token usage
- Protected endpoints require header:
  - `Authorization: Bearer <access_token>`

---

## 3) User & Profile APIs

These endpoints manage the user's profile and bank verification.

### Get current user
- Purpose: Return basic authenticated user info and profile completion state.
- Method: GET
- URL: `/api/auth/me/`
- Auth: Required
- Success (200):

```json
{ "id": 1, "name": "Alice", "email": "alice@example.com", "profile": { "is_completed": false } }
```

### Update personal information (draft)
- Purpose: Save personal information in `profile.draft_payload.personal` (not committed until verification).
- Method: PATCH
- URL: `/api/profile/personal/`
- Auth: Required
- Request payload example:

```json
{
  "first_name": "Alice",
  "surname": "Example",
  "phone_number": "2348012345678",
  "date_of_birth": "1990-01-01",
  "gender": "F"
}
```

- Validation rules:
  - `date_of_birth` must be in the past.
  - `phone_number` must contain digits; canonical format enforced at mandate creation time (`234XXXXXXXXXX`).

- Success (200): returns the saved draft personal fields (subset returned without nulls).
- Errors (400): validation errors.

### Update bank information (draft)
- Purpose: Save bank details to `profile.draft_payload.bank`. Sensitive fields are encrypted (Fernet) at rest.
- Method: PATCH
- URL: `/api/profile/bank/`
- Auth: Required
- Request payload example:

```json
{
  "account_number": "0123456789",
  "bank_name": "Access Bank",
  "bank_code": "044",
  "bvn": "12345678901"
}
```

- Validation rules:
  - `account_number` must be exactly 10 digits.
  - `bvn` must be exactly 11 digits.
  - `bank_code` must be present.

- Success (200): returns non-sensitive bank summary `{ "bank_name": ..., "bank_code": ... }`.
- Errors (400): validation errors.

### Submit profile for verification
- Purpose: Submit personal + bank draft to OnePipe to verify account ownership (OnePipe `lookup accounts min`). On success the draft is copied to final profile fields and `profile.is_completed` is set to `true`.
- Method: POST
- URL: `/api/profile/submit/`
- Auth: Required
- Preconditions: `draft_payload.personal` and `draft_payload.bank` must exist.
- What KORE does internally: builds a payload via `build_lookup_accounts_min_payload()` (which encrypts account details using TripleDES for `auth.secure`) and calls `OnePipeClient.transact()`.
- Success: profile fields updated, `profile.is_completed = true`, `ProfileVerificationAttempt` logged, response 200.
- Failure: response 400 with provider response details; a `ProfileVerificationAttempt` with `failed` status is stored.

---

## 4) Services API

Used by the frontend to present service categories when creating a rules engine.

- Endpoint: GET `/api/services/`
- Auth: No (public)
- Purpose: Return a small, static, ordered list of supported service categories.
- Response example (200):

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

Notes:
- Keys are uppercase and stable for backend usage. Labels are human-friendly for UI.
- Order is preserved.

---

## 5) Rules Engine APIs

Per-user debit rules that control how much and how often money can be debited.
Only one active `RulesEngine` per user is allowed (the application enforces this).

### Create Rules Engine
- Method: POST
- URL: `/api/rules-engine/`
- Auth: Required
- Request payload example:

```json
{
  "monthly_max_debit": 50000.00,
  "single_max_debit": 10000.00,
  "frequency": "MONTHLY",
  "amount_per_frequency": 50000.00,
  "allocations": [
    { "bucket": "SAVINGS", "percentage": 50 },
    { "bucket": "SPENDING", "percentage": 50 }
  ],
  "failure_action": "NOTIFY",
  "start_date": "2026-02-01",
  "end_date": null
}
```

- Key fields explained:
  - `frequency`: one of `DAILY`, `WEEKLY`, `MONTHLY`, `CUSTOM`.
  - `allocations`: percentage-based list; each item requires `bucket` (string) and `percentage` (number). Percentages must sum to exactly 100.
  - `start_date` / `end_date`: define the active window for the rule. If `end_date` is present it must be after `start_date`.

- Validation rules:
  - Numeric debit fields must be positive.
  - `single_max_debit` cannot exceed `monthly_max_debit`.
  - `allocations` must be a non-empty list and total 100.

- Success (201): returns saved rule and `"ready_for_mandate": true`.
- Errors (400): validation errors.

### Get active rules engine
- Method: GET
- URL: `/api/rules-engine/me/`
- Auth: Required
- Success (200): returns current active RulesEngine.
- Not found (404): `{ "error": "No rules engine configured yet." }`

### Update active rules engine
- Method: PATCH
- URL: `/api/rules-engine/me/`
- Auth: Required
- Purpose: Partially update the active rule (numeric/frequency/allocations/dates).
- Success (200): updated rule
- Errors (400/404): validation or missing active rule

### Disable active rules engine
- Method: POST
- URL: `/api/rules-engine/me/disable/`
- Auth: Required
- Purpose: Soft-disable the active rule (`is_active = false`).
- Success (200): `{ "message": "Rules engine disabled" }`
- Not found (404): if no active rule exists.

---

## 6) Mandate APIs (PayWithAccount Integration)

KORE integrates with OnePipe PayWithAccount to create and cancel mandates. The code uses `OnePipeClient.transact()` and builders in `api/onepipe_client.py`.

### Preconditions for mandate actions
- `profile.is_completed` must be `true` before creating a mandate.
- An active `RulesEngine` must exist for the user when creating a mandate.
- At mandate time the profile must include `first_name`, `surname`, and `phone_number` (canonical `234XXXXXXXXXX` format).

### Create mandate (tokenize account)
- Method: POST
- URL: `/api/mandates/create/`
- Auth: Required
- Request payload (client → KORE):

```json
{ "customer_consent": "<optional base64 string>" }
```

- What KORE does internally:
  - Decrypts profile encrypted fields in-memory (account number and BVN), builds a payload with `build_create_mandate_payload()`.
  - Uses TripleDES to encrypt provider-required fields (auth.secure) and meta (bvn) before sending to OnePipe.
  - Signs requests using `Signature: MD5(request_ref;CLIENT_SECRET)` (lowercase hex) and sends `Authorization: Bearer {ONEPIPE_API_KEY}`.

- Success (201): KORE persists a `Mandate` record with fields such as `mandate_reference`, `subscription_id`, `provider_response`, and sets `status` to `ACTIVE` when provider indicates activation, otherwise `PENDING`.
  - Example response:

```json
{
  "id": 42,
  "status": "PENDING",
  "request_ref": "abc123",
  "activation_url": "https://provider/activate"
}
```

- Errors: provider errors (400) or transport errors (502). On transport errors KORE stores a `FAILED` mandate record for audit.

### Get my mandate
- Method: GET
- URL: `/api/mandates/me/`
- Auth: Required
- Purpose: Return the latest `Mandate` for the authenticated user (ordered by `created_at` desc).
- Success (200): Example:

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

- Not found (404): `{ "error": "No mandate found for this user." }`

### Cancel mandate
- Method: POST
- URL: `/api/mandates/cancel/`
- Auth: Required
- Preconditions: latest ACTIVE mandate must exist and `mandate_reference` must be set; profile must have required personal fields.
- Request payload (client → KORE): `{}` (no body required)

- What KORE sends to OnePipe internally:
  - `request_type: "Cancel Mandate"`
  - `auth`: `{ "type": null, "secure": null, "auth_provider": "PaywithAccount" }`
  - `transaction.meta.payment_id` set to `mandate.mandate_reference`
  - Customer fields from profile (firstname, surname, email, mobile_no)

- Success condition (exact):
  - `response["status"] == "Successful"` AND `response["data"]["provider_response_code"] == "00"`

- On success (200):
  - Mandate updated: `status = "CANCELLED"`, `cancel_response` saved, `cancelled_at` set.
  - Response:

```json
{ "message": "Mandate cancelled", "mandate_status": "CANCELLED" }
```

- On failure (400):
  - Mandate remains `ACTIVE`; `cancel_response` saved; provider response returned to caller.

- On transport error (502): saved audit info and returned 502.

---

## 7) Webhooks

### OnePipe webhook
- Endpoint: POST `/api/webhooks/onepipe/`
- Auth: None (public endpoint for provider callbacks)
- Purpose: Receives OnePipe webhook events. KORE stores the raw payload as `WebhookEvent` and attempts to associate with `ProfileVerificationAttempt` using `request_ref`.
- Processing: Non-blocking; returns 200 OK quickly to avoid retries. Payloads vary by provider and are stored raw for auditing and manual inspection.

---

## 8) Common Response Formats

- Success responses vary by endpoint; commonly HTTP 200 or 201 with JSON objects.

- Standard error responses include an `error` or `message` field. Examples:

400 Bad Request (validation or provider failure):

```json
{ "error": "Validation error details" }
```

401 Unauthorized (missing/invalid token):

```json
{ "detail": "Authentication credentials were not provided." }
```

404 Not Found:

```json
{ "error": "No mandate found for this user." }
```

502 Bad Gateway (OnePipe transport errors):

```json
{ "message": "Failed to contact OnePipe", "details": "<error details>" }
```

---

## 9) Environment & Configuration (High Level)

KORE expects OnePipe configuration in `settings.ONEPIPE` (a dict). Do NOT commit secrets.

Required keys (examples, do NOT include values here):
- `API_KEY` — OnePipe API key (used as `Authorization: Bearer ...`).
- `CLIENT_SECRET` — OnePipe client secret (used for signature generation and TripleDES key derivation).
- `BASE_URL` — OnePipe base URL (e.g., `https://api.onepipe.io`).
- `TRANSACT_PATH` — API path for transact (e.g., `/v2/transact`).
- `ONEPIPE_BILLER_CODE` or `BILLER_CODE` — biller code included in `meta` of create/cancel payloads.
- Optional: `WEBHOOK_URL` — URL included in payloads for provider callbacks.

Other application configuration (standard Django envs) include DB settings, cache backend, and secret key.

---

## 10) Notes & Constraints

- Amounts: When constructing OnePipe payloads, some amounts are multiplied by 1000 (e.g., `monthly_max_debit * 1000`) to match provider conventions.
- Phone format: Phone numbers must be canonical `234XXXXXXXXXX` (13 digits). Validation enforces this for mandate operations.
- RulesEngine: Only one active rule per user. Creating a new rule deactivates prior active rules for that user.
- Mandates: The system expects and uses the latest ACTIVE mandate for cancellation.
- Sensitive data handling:
  - Account numbers and BVNs are encrypted at rest using Fernet.
  - Provider-specific TripleDES encryption used for payload fields is performed in memory before sending; KORE does not store plaintext account numbers.
- Request signing: OnePipe requests are signed with `Signature: MD5(request_ref;CLIENT_SECRET)` (UTF-8) — signature bytes are hex-lowercase.
- Provider responses are stored in `Mandate.provider_response` and cancel responses in `Mandate.cancel_response` for auditing.

---

## Appendix: Example curl snippets

Obtain token (login):

```bash
curl -X POST https://<host>/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{ "email": "alice@example.com", "password": "secret123" }'
```

Get services (public):

```bash
curl https://<host>/api/services/
```

Create rules engine (authenticated):

```bash
curl -X POST https://<host>/api/rules-engine/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access_token>' \
  -d '{ "monthly_max_debit": 50000, "single_max_debit": 10000, "frequency": "MONTHLY", "amount_per_frequency": 50000, "allocations": [{"bucket":"SAVINGS","percentage":50},{"bucket":"SPENDING","percentage":50}], "failure_action":"NOTIFY", "start_date":"2026-02-01" }'
```

Create mandate (authenticated):

```bash
curl -X POST https://<host>/api/mandates/create/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access_token>' \
  -d '{ "customer_consent": "" }'
```

Cancel mandate (authenticated):

```bash
curl -X POST https://<host>/api/mandates/cancel/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access_token>' \
  -d '{}'
```

---

If you want, I can:
- Generate a Swagger/OpenAPI skeleton derived from these endpoints.
- Produce example Postman collection exported from these routes.
- Add `curl` examples for failure cases and detailed JSON schema blocks for each model.

---

File: `docs/API_DOCUMENTATION.md` created.
