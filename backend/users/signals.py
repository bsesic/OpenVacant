"""Account lifecycle emails: welcome on email confirmation, login notifications."""

from allauth.account.signals import email_confirmed
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from users.emails import send_transactional_mail


@receiver(email_confirmed)
def send_welcome_email(request, email_address, **kwargs):
    """Send a welcome email once a user verifies their email address."""
    send_transactional_mail(
        subject_template="emails/welcome_subject.txt",
        body_template="emails/welcome_body.txt",
        context={"user": email_address.user},
        recipient_list=[email_address.email],
    )


@receiver(user_logged_in)
def send_login_notification(sender, request, user, **kwargs):
    """Notify the user of a new sign-in (a basic security signal)."""
    if not user.email:
        return
    context = {
        "user": user,
        "ip": request.META.get("REMOTE_ADDR", "") if request else "",
        "user_agent": request.META.get("HTTP_USER_AGENT", "") if request else "",
    }
    send_transactional_mail(
        subject_template="emails/login_notification_subject.txt",
        body_template="emails/login_notification_body.txt",
        context=context,
        recipient_list=[user.email],
    )
