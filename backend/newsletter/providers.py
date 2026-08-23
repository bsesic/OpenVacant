"""Newsletter provider hook.

Newsletter delivery is provider-specific (Brevo, Mailchimp, Listmonk, ...), so the
boilerplate ships only this seam. Override ``sync_subscriber`` per project to push the
subscriber to your ESP (e.g. add/remove a contact in a list) once they confirm or
unsubscribe.
"""


def sync_subscriber(subscriber):
    """No-op by default. Implement per project to sync with an external provider."""
    return None
