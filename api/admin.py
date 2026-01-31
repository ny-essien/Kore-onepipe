from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Profile
from .admin_forms import CustomUserCreationForm, CustomUserChangeForm


# Custom User admin with email field and full name support
class CustomUserAdmin(UserAdmin):
    """
    Custom User admin to include email and full name in the user creation form.
    
    Overrides the default Django User admin to:
    - Remove username field (auto-generated from email)
    - Add email field (required) when creating users
    - Show "Full name" field instead of separate first_name/last_name
    - Display email in the user list
    - Allow searching by email
    - Validate email uniqueness
    """
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    # Fields shown when adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )
    
    # Fields shown when editing an existing user
    fieldsets = (
        (None, {'fields': ('email', 'full_name')}),
        ('Personal info', {'fields': ('last_name',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    list_display = ('email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')


# Re-register the User admin with custom configuration
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "get_user_email",
        "first_name",
        "surname",
        "phone_number",
        "is_completed",
        "created_at",
    )
    list_filter = ("is_completed", "gender", "created_at", "updated_at")
    search_fields = (
        "user__email",
        "user__username",
        "first_name",
        "surname",
        "phone_number",
    )
    readonly_fields = ("created_at", "updated_at", "user")
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "User",
            {"fields": ("user",)},
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "surname",
                    "phone_number",
                    "date_of_birth",
                    "gender",
                )
            },
        ),
        (
            "Bank Information",
            {
                "fields": (
                    "bank_name",
                    "bank_code",
                    "account_number_encrypted",
                    "bvn_encrypted",
                ),
                "classes": ("collapse",),  # Hide by default for security
            },
        ),
        (
            "Status",
            {"fields": ("is_completed",)},
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = "Email"
    get_user_email.admin_order_field = "user__email"
