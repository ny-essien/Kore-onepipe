from django.contrib import admin
from .models import Profile


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
