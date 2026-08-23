import secrets

from django.db import models


def generate_token():
    return secrets.token_urlsafe(32)


class Subscriber(models.Model):
    """A newsletter subscriber with double opt-in and one-click unsubscribe."""

    email = models.EmailField(unique=True)
    confirmed = models.BooleanField(default=False)
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return self.confirmed and self.unsubscribed_at is None
