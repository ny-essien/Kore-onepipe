"""
Django signals for the api app.

Auto-creates a Profile when a User is created (admin, API, or any other path).

Why signals?
- Ensures Profile is created regardless of how User is created (admin, API, CLI, etc.)
- Decouples Profile creation from business logic
- Prevents duplicate Profiles using get_or_create()
- Guarantees every User always has a corresponding Profile
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def create_profile(sender, instance, created, **kwargs):
    """
    Auto-create a Profile when a User is created.
    
    This signal ensures that:
    - Admin user creation automatically gets a Profile
    - API signup always has a Profile ready
    - Any other User creation path (CLI, scripts, etc.) gets a Profile
    - If Profile already exists, get_or_create prevents duplicates
    """
    if created:
        from .models import Profile
        profile, created_profile = Profile.objects.get_or_create(
            user=instance,
            defaults={"first_name": instance.first_name}
        )
        if created_profile:
            logger.info(f"Profile auto-created for user: {instance.username}")


# Connect the signal explicitly with dispatch_uid to prevent duplicate connections
post_save.connect(create_profile, sender=User, dispatch_uid="create_profile_for_user")
