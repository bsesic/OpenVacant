"""Email helpers with an explicit transactional/marketing split."""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_transactional_mail(subject_template, body_template, context, recipient_list):
    """Render and send a transactional email from the transactional sender.

    Subject and body are rendered from templates so copy stays out of the code.
    """
    subject = render_to_string(subject_template, context).strip()
    body = render_to_string(body_template, context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.TRANSACTIONAL_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=False,
    )


# Marketing/bulk email should go through a separate sender (and ideally a
# separate ESP API key) to protect transactional deliverability. A project that
# needs it can mirror send_transactional_mail() using settings.MARKETING_FROM_EMAIL.
