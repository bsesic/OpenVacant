"""Retention rules.

Keeping data for as long as it happens to be convenient is the failure mode the
deletion concept exists to prevent. Each rule below answers one question: how
long does this actually need to exist?
"""

import datetime

from django.conf import settings
from django.utils import timezone


def _cutoff(days):
    return timezone.now() - datetime.timedelta(days=days)


def purge_discarded_reports(days=None):
    """Delete reports that were rejected or marked as spam long enough ago.

    An unfounded accusation about a building should not sit in the register
    indefinitely. Reports that led somewhere are kept: they are part of the
    record's provenance.
    """
    from apps.reports.models import DISCARDED_REPORT_STATUSES, Report

    days = settings.REPORT_REJECTED_RETENTION_DAYS if days is None else days
    stale = Report.objects.filter(
        status__in=DISCARDED_REPORT_STATUSES,
        updated_at__lt=_cutoff(days),
        property__isnull=True,
    )
    count = stale.count()
    stale.delete()
    return count


def anonymise_report_origins(days=30):
    """Drop the submitting IP address once it can no longer serve its purpose.

    The address is kept only to deal with abuse. After a month it is of no use
    for that and is simply a record of where somebody was.
    """
    from apps.reports.models import Report

    return Report.objects.filter(
        submitted_from_ip__isnull=False, created_at__lt=_cutoff(days)
    ).update(submitted_from_ip=None)


def purge_access_log(days=None):
    """Delete audit entries past their retention period.

    The log is itself a record of what staff did, so it is not kept forever
    either.
    """
    from compliance.models import AccessLog

    days = settings.AUDIT_LOG_RETENTION_DAYS if days is None else days
    stale = AccessLog.objects.filter(created_at__lt=_cutoff(days))
    count = stale.count()
    stale.delete()
    return count


def strip_contact_details_of_declined_feedback():
    """Remove contact details nobody asked us to keep.

    A reporter who did not ask to hear back has no reason for their address to
    remain on the report once it has been moderated.
    """
    from apps.reports.models import OPEN_REPORT_STATUSES, Report

    return Report.objects.filter(wants_feedback=False).exclude(
        status__in=OPEN_REPORT_STATUSES
    ).exclude(
        contact_email="", contact_phone="", contact_name=""
    ).update(contact_email="", contact_phone="", contact_name="")


def run_all():
    """Apply every rule, returning what each one did."""
    return {
        "discarded_reports_deleted": purge_discarded_reports(),
        "report_origins_anonymised": anonymise_report_origins(),
        "contact_details_stripped": strip_contact_details_of_declined_feedback(),
        "access_log_entries_deleted": purge_access_log(),
    }
