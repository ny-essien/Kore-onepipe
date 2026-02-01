# GET /api/mandates/me/ Endpoint Implementation

## Summary

Added a "Get My Mandate" endpoint that returns the latest mandate for the authenticated user with full status and identifier information.

## Changes Made

### A. MandateSerializer (api/serializers.py)
Created a new `MandateSerializer` that returns:
- `id` - Mandate primary key
- `status` - PENDING/ACTIVE/FAILED/CANCELLED
- `mandate_reference` - Provider mandate identifier (blank if not set)
- `subscription_id` - Provider subscription id (null if not set)
- `request_ref` - Internal request reference
- `activation_url` - Authorization/activation URL (blank if not set)
- `created_at` - Mandate creation timestamp
- `cancelled_at` - Cancellation timestamp (null if not cancelled)
- `provider_response_code` - Extracted from provider responses (optional)

The serializer:
- Does NOT return sensitive bank data
- Extracts `provider_response_code` from `cancel_response` (preferred) or `provider_response`
- Returns None if no provider response code available

### B. Updated MandatesMeView (api/views.py)
Modified `MandatesMeView` to:
- Use the new `MandateSerializer` for consistent response format
- Return correct error message: "No mandate found for this user." (404)
- Only return the latest mandate ordered by `created_at` descending

### C. URLs
Route already registered in `api/urls.py`:
- `GET /api/mandates/me/` → `MandatesMeView`

### D. Tests (api/test_get_mandate.py)
Created 7 comprehensive tests covering:
1. **No auth** → 401 Unauthorized
2. **No mandates** → 404 with "No mandate found for this user."
3. **Single mandate** → 200 with all fields
4. **Multiple mandates** → 200 with latest mandate (newest by created_at)
5. **Cancelled status** → Returns status=CANCELLED and cancelled_at timestamp
6. **Pending status** → Returns status=PENDING correctly
7. **Missing optional fields** → Handles missing mandate_reference, subscription_id, activation_url gracefully

All tests pass ✓

## Response Examples

### Success (200 OK)
```json
{
  "id": 42,
  "status": "ACTIVE",
  "mandate_reference": "mandate-ref-123",
  "subscription_id": 789,
  "request_ref": "request-ref-abc123",
  "activation_url": "https://example.com/activate",
  "created_at": "2026-02-01T10:30:00Z",
  "cancelled_at": null,
  "provider_response_code": "00"
}
```

### No Mandate (404 Not Found)
```json
{
  "error": "No mandate found for this user."
}
```

### Not Authenticated (401 Unauthorized)
```json
{
  "detail": "Authentication credentials were not provided."
}
```

## Integration Notes

- The endpoint requires JWT authentication (Bearer token)
- Returns the most recent mandate by creation date
- Safe to expose all mandate fields (no sensitive bank data)
- provider_response_code is extracted intelligently from cancel/provider responses
- All date fields are ISO 8601 formatted

## Running Tests

```bash
py manage.py test api.test_get_mandate -v2
```

Result: 7/7 tests passed ✓
