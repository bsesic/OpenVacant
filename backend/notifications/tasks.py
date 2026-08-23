from celery import shared_task

from notifications.models import notify


@shared_task
def send_notification_async(user_id, verb, url=""):
    """Example background task: create an in-app notification off-request."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        return None
    notification = notify(user, verb, url=url)
    return notification.pk
