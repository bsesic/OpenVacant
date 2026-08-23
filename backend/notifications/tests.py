import pytest
from django.urls import reverse

from notifications.models import Notification, notify


@pytest.mark.django_db
def test_notify_creates_unread_notification(make_user):
    user = make_user(username="n1")
    note = notify(user, "Something happened", url="/x/")
    assert note.unread is True
    assert user.notifications.unread().count() == 1


@pytest.mark.django_db
def test_notifications_are_per_user(client, make_user):
    a = make_user(username="na")
    b = make_user(username="nb")
    notify(a, "For A")
    client.force_login(b)
    response = client.get(reverse("notifications:list"))
    assert b"For A" not in response.content


@pytest.mark.django_db
def test_mark_read(client, make_user):
    user = make_user(username="nr")
    note = notify(user, "Read me")
    client.force_login(user)
    response = client.post(reverse("notifications:mark_read", args=[note.pk]))
    assert response.status_code == 302
    note.refresh_from_db()
    assert note.unread is False


@pytest.mark.django_db
def test_mark_all_read(client, make_user):
    user = make_user(username="nall")
    notify(user, "one")
    notify(user, "two")
    client.force_login(user)
    client.post(reverse("notifications:mark_all_read"))
    assert Notification.objects.filter(recipient=user, unread=True).count() == 0


@pytest.mark.django_db
def test_send_notification_async_eager(make_user):
    from notifications.tasks import send_notification_async

    user = make_user(username="celery1")
    note_pk = send_notification_async.delay(user.id, "Async hello").get()
    assert Notification.objects.filter(pk=note_pk, recipient=user, verb="Async hello").exists()
