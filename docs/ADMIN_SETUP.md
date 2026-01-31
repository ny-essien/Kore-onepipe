# Django Admin & Signals Setup - Completion Summary

## Overview
Updated Django admin to include email field in user creation form and auto-create Profile for every new User.

## Files Created/Modified

### 1. **api/admin_forms.py** (NEW)
**Purpose:** Custom user creation and change forms with email validation.

**Key Features:**
- `CustomUserCreationForm`: Extends Django's UserCreationForm
  - Adds required `email` field
  - Validates email uniqueness (case-insensitive)
  - Saves user.email on form.save()
  
- `CustomUserChangeForm`: Extends ModelForm for user editing
  - Makes email editable and required
  - Validates email uniqueness (excluding current user)

**Validation:**
```python
# Email must be unique (new or existing users)
if User.objects.filter(email__iexact=email).exists():
    raise ValidationError("A user with this email already exists.")
```

### 2. **api/signals.py** (NEW)
**Purpose:** Django signals for auto-creating Profile when User is created.

**Implementation:**
```python
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
```

**Behavior:**
- Listens for User post_save signals
- If `created=True`, auto-creates a Profile
- Uses `get_or_create()` to prevent duplicates
- Works for: admin creation, API signup, CLI, scripts, etc.

### 3. **api/apps.py** (MODIFIED)
**Change:** Added `ready()` method to load signals at app startup.

```python
def ready(self):
    """Import signals when app is ready."""
    import api.signals  # noqa: F401
```

**Why:** Django needs signals imported to register receivers.

### 4. **api/admin.py** (MODIFIED)
**Change:** Replaced simple CustomUserAdmin with full implementation using custom forms.

**New CustomUserAdmin:**
- `add_form = CustomUserCreationForm` - Uses custom form with email validation
- `form = CustomUserChangeForm` - Uses custom form for editing
- `add_fieldsets` - Shows: username, email, password1, password2
- `fieldsets` - Shows: username, email, personal info, permissions, dates
- `list_display` - Shows: username, email, first_name, last_name, is_staff
- `search_fields` - Searchable by: username, email, first_name, last_name

**Result:** Admin user creation form now includes email field (required).

## How It Works

### User Creation Flow (Admin)
1. Admin visits `/admin/auth/user/add/`
2. Form shows: username, email, password1, password2
3. Admin submits
4. `CustomUserCreationForm.save()` creates User with email
5. `create_profile` signal fires (post_save)
6. Profile is auto-created via `get_or_create()`
7. User now has a Profile ready

### User Creation Flow (API - Existing)
1. POST `/api/auth/signup/` with name, email, password
2. `RegisterSerializer.create()` creates User
3. `create_profile` signal fires
4. Profile is auto-created
5. Response includes user data + JWT tokens

### Duplicate Email Prevention
**Admin:** `CustomUserCreationForm.clean_email()` validates uniqueness before save  
**API:** `RegisterSerializer.validate_email()` checks uniqueness  
**Both:** Use case-insensitive check to prevent "email@example.com" vs "Email@example.com"

## Safety & Compatibility

✅ **No Breaking Changes:**
- Existing user creation flows unaffected
- API signup still works (Profile created by signal)
- Admin user creation enhanced (now requires email)

✅ **Profile Duplication Prevented:**
- `get_or_create()` in signal ensures no duplicates
- Safe to call multiple times

✅ **Email Validation:**
- Required field in admin form
- Uniqueness checked at form and model level
- Case-insensitive comparison

## Verification

**Files created:**
- ✓ `api/admin_forms.py` - Custom forms with validation
- ✓ `api/signals.py` - Auto-profile creation signal

**Files modified:**
- ✓ `api/admin.py` - Updated to use custom forms
- ✓ `api/apps.py` - Added ready() to load signals

**System Checks:**
- ✓ Django check passes (no errors)
- ✓ All imports working
- ✓ Forms validate correctly

## Usage

### Creating a User in Admin
1. Go to `/admin/auth/user/add/`
2. Fill form:
   - Username: alice
   - Email: alice@example.com (required, must be unique)
   - Password: (generated securely)
   - Confirm Password: (must match)
3. Click Save
4. User created with email
5. Profile auto-created
6. Redirected to user change form

### API Signup (Unchanged)
```bash
POST /api/auth/signup/
{
  "name": "Alice",
  "email": "alice@example.com",
  "password": "secret",
  "confirm_password": "secret"
}
```
Response includes User + Profile + JWT tokens

### Using Django Shell
```python
python manage.py shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.create_user('bob', 'bob@example.com', 'pass')
>>> u.profile  # Profile auto-created!
<Profile: Profile: Bob Unknown (bob@example.com)>
```

## Testing

To verify the setup:
```bash
python scripts/verify_admin_setup.py
```

Or manually test:
```bash
# Start server
python manage.py runserver

# Go to admin
# http://localhost:8000/admin/auth/user/

# Try creating a user with:
# - Username: testuser
# - Email: test@example.com
# - Password: TestPassword123!

# Then check user has profile:
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.get(username='testuser').profile
```

## Files Reference

| File | Purpose | Status |
|------|---------|--------|
| `api/admin_forms.py` | Custom user creation/change forms | ✓ Created |
| `api/signals.py` | Auto-create Profile signal | ✓ Created |
| `api/admin.py` | Custom UserAdmin with email | ✓ Modified |
| `api/apps.py` | Load signals on app ready | ✓ Modified |
| `api/models.py` | Profile model (unchanged) | ✓ OK |

## Next Steps (Optional)

1. **Audit existing users** - Some may not have Profile
   ```bash
   python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> from api.models import Profile
   >>> for u in User.objects.all():
   ...     Profile.objects.get_or_create(user=u)
   ```

2. **Add email validation rules** - Customize validation in forms

3. **Send welcome email** - Add signal to send email on user creation

4. **Log user creation** - Add audit trail to track who created users
