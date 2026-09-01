from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model. Extend with platform-specific profile fields as needed."""

    # GDPR soft-delete: set when the user requests deletion; a cron purges later.
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
