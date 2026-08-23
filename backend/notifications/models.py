from django.conf import settings
from django.db import models


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(unread=True)


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    verb = models.CharField(max_length=255)
    url = models.CharField(max_length=500, blank=True)
    unread = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient}: {self.verb}"


def notify(recipient, verb, url="", organization=None):
    """Create an in-app notification. Call this from anywhere in the app."""
    return Notification.objects.create(
        recipient=recipient, verb=verb, url=url, organization=organization
    )
