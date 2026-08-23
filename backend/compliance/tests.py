from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
def test_data_export_requires_login(client):
    assert client.get(reverse("compliance:data_export")).status_code == 302


@pytest.mark.django_db
def test_data_export_returns_json(client, make_user):
    user = make_user(username="exp", email="exp@example.com")
    client.force_login(user)
    response = client.get(reverse("compliance:data_export"))
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert response.json()["user"]["email"] == "exp@example.com"


@pytest.mark.django_db
def test_account_delete_soft_deletes(client, make_user):
    user = make_user(username="del")
    client.force_login(user)
    response = client.post(reverse("compliance:account_delete"))
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.is_active is False
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
def test_purge_command_deletes_expired_accounts(make_user):
    expired = make_user(username="old")
    expired.deletion_requested_at = timezone.now() - timedelta(days=40)
    expired.save(update_fields=["deletion_requested_at"])
    keep = make_user(username="keep")

    call_command("purge_deleted_accounts")

    assert not User.objects.filter(pk=expired.pk).exists()
    assert User.objects.filter(pk=keep.pk).exists()


@pytest.mark.django_db
def test_sitemap_and_robots(client):
    sitemap = client.get(reverse("sitemap"))
    assert sitemap.status_code == 200
    assert b"/about/" in sitemap.content

    robots = client.get(reverse("robots"))
    assert robots.status_code == 200
    assert robots["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_contact_form_is_rate_limited(client):
    cache.clear()
    url = reverse("pages:contact")
    payload = {"name": "Sam", "email": "sam@example.com", "message": "Hi there"}
    statuses = [client.post(url, payload).status_code for _ in range(6)]
    assert statuses[-1] == 403
    assert statuses[0] in (200, 302)


# --- Access log ------------------------------------------------------------


@pytest.mark.django_db
def test_viewing_a_report_with_contact_details_is_logged(client, municipal_staff):
    from apps.reports.models import Report
    from compliance.models import AccessCategory, AccessLog

    staff, organization, _municipality = municipal_staff(username="audit_staff")
    report = Report.objects.create(
        organization=organization,
        city="Town",
        contact_name="Anna Beispiel",
        contact_email="anna@example.com",
    )

    client.force_login(staff)
    client.get(reverse("reports:detail", args=[report.pk]))

    entry = AccessLog.objects.get()
    assert entry.category == AccessCategory.REPORTER_CONTACT
    assert entry.actor == staff
    # The label survives the account being deleted, which is when it matters.
    assert entry.actor_label == str(staff)
    assert entry.object_reference == report.reference


@pytest.mark.django_db
def test_a_report_without_personal_data_is_not_logged(client, municipal_staff):
    from apps.reports.models import Report
    from compliance.models import AccessLog

    staff, organization, _municipality = municipal_staff(username="audit_staff2")
    report = Report.objects.create(organization=organization, city="Town")

    client.force_login(staff)
    client.get(reverse("reports:detail", args=[report.pk]))
    # Logging every page view would bury the entries that matter.
    assert AccessLog.objects.count() == 0


@pytest.mark.django_db
def test_a_refused_request_records_nothing(client, make_user, municipal_staff):
    from apps.reports.models import Report
    from compliance.models import AccessLog

    _staff, organization, _municipality = municipal_staff(username="audit_staff3")
    report = Report.objects.create(
        organization=organization, city="Town", contact_email="a@example.com"
    )
    citizen = make_user(username="audit_citizen")

    client.force_login(citizen)
    assert client.get(reverse("reports:detail", args=[report.pk])).status_code == 403
    assert AccessLog.objects.count() == 0


@pytest.mark.django_db
def test_viewing_a_record_logs_the_internal_notes_access(client, municipal_staff):
    from apps.properties.models import Property
    from compliance.models import AccessCategory, AccessLog

    staff, organization, _municipality = municipal_staff(username="audit_staff4")
    record = Property.objects.create(organization=organization, street="Aktenweg")

    client.force_login(staff)
    client.get(record.get_absolute_url())
    entry = AccessLog.objects.get()
    assert entry.category == AccessCategory.INTERNAL_NOTES
    assert entry.object_reference == record.reference


@pytest.mark.django_db
def test_exports_are_logged(client, municipal_staff):
    from compliance.models import AccessCategory, AccessLog

    staff, _organization, _municipality = municipal_staff(username="audit_staff5")
    client.force_login(staff)
    client.get(reverse("statistics:export"))
    assert AccessLog.objects.filter(category=AccessCategory.BULK_EXPORT).exists()

    client.get(reverse("compliance:data_export"))
    assert AccessLog.objects.filter(category=AccessCategory.DATA_EXPORT).exists()


@pytest.mark.django_db
def test_only_managers_can_read_the_access_log(client, municipal_staff, make_member):
    from organizations.models import Role

    _staff, organization, _municipality = municipal_staff(username="audit_staff6")
    planner, _org = make_member(
        role=Role.URBAN_PLANNING, organization=organization, username="audit_planner"
    )
    manager, _org2 = make_member(
        role=Role.OWNER, organization=organization, username="audit_manager"
    )

    client.force_login(planner)
    assert client.get(reverse("compliance:access_log")).status_code == 403

    client.force_login(manager)
    assert client.get(reverse("compliance:access_log")).status_code == 200


@pytest.mark.django_db
def test_the_access_log_is_scoped_to_the_municipality(client, municipal_staff, make_member):
    from compliance.audit import log_access
    from compliance.models import AccessCategory
    from organizations.models import Role

    _staff, organization, _municipality = municipal_staff(username="audit_staff7")
    other_manager, other_org, _mun = municipal_staff(
        role=Role.OWNER, username="audit_other_manager"
    )
    log_access(
        None, AccessCategory.OWNER_DATA, organization=organization, object_reference="SECRET-REF"
    )

    client.force_login(other_manager)
    body = client.get(reverse("compliance:access_log")).content.decode()
    assert "SECRET-REF" not in body


# --- Consent ---------------------------------------------------------------


@pytest.mark.django_db
def test_submitting_a_report_evidences_the_consent(make_municipality):
    from apps.reports.models import Report
    from compliance.models import ConsentPurpose, ConsentRecord
    from django.utils import timezone

    municipality = make_municipality(name="Consent town")
    report = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        consent_given_at=timezone.now(),
    )
    consent = ConsentRecord.objects.get(purpose=ConsentPurpose.REPORT_SUBMISSION)
    assert consent.subject_label == report.reference
    assert consent.is_active
    assert consent.source == "report form"


@pytest.mark.django_db
def test_asking_for_feedback_records_a_second_consent(make_municipality):
    from apps.reports.models import Report
    from compliance.models import ConsentPurpose, ConsentRecord
    from django.utils import timezone

    municipality = make_municipality(name="Feedback town")
    Report.objects.create(
        organization=municipality.organization,
        city="Town",
        consent_given_at=timezone.now(),
        wants_feedback=True,
        contact_email="anna@example.com",
    )
    purposes = set(ConsentRecord.objects.values_list("purpose", flat=True))
    assert purposes == {
        ConsentPurpose.REPORT_SUBMISSION,
        ConsentPurpose.FEEDBACK_CONTACT,
    }


@pytest.mark.django_db
def test_consent_can_be_withdrawn_and_stays_evidenced(make_municipality):
    from apps.reports.models import Report
    from compliance.models import ConsentRecord
    from django.utils import timezone

    municipality = make_municipality(name="Withdraw town")
    Report.objects.create(
        organization=municipality.organization,
        city="Town",
        consent_given_at=timezone.now(),
    )
    consent = ConsentRecord.objects.first()
    consent.withdraw()
    assert consent.is_withdrawn
    assert not consent.is_active
    # Withdrawing does not erase that it was given.
    assert consent.granted_at is not None


@pytest.mark.django_db
def test_consent_survives_the_report_being_deleted(make_municipality):
    from apps.reports.models import Report
    from compliance.models import ConsentRecord
    from django.utils import timezone

    municipality = make_municipality(name="Deleted town")
    report = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        consent_given_at=timezone.now(),
    )
    report.delete()
    assert ConsentRecord.objects.count() == 1


# --- Retention -------------------------------------------------------------


@pytest.mark.django_db
def test_discarded_reports_are_deleted_after_the_retention_period(make_municipality):
    import datetime

    from apps.reports.models import Report, ReportStatus
    from compliance import retention
    from django.utils import timezone

    municipality = make_municipality(name="Retention town")
    old_spam = Report.objects.create(
        organization=municipality.organization, city="Town", status=ReportStatus.SPAM
    )
    kept = Report.objects.create(
        organization=municipality.organization, city="Town", status=ReportStatus.ACCEPTED
    )
    recent_spam = Report.objects.create(
        organization=municipality.organization, city="Town", status=ReportStatus.SPAM
    )
    Report.objects.filter(pk=old_spam.pk).update(
        updated_at=timezone.now() - datetime.timedelta(days=400)
    )

    deleted = retention.purge_discarded_reports()
    assert deleted == 1
    assert not Report.objects.filter(pk=old_spam.pk).exists()
    assert Report.objects.filter(pk=kept.pk).exists()
    assert Report.objects.filter(pk=recent_spam.pk).exists()


@pytest.mark.django_db
def test_a_discarded_report_attached_to_a_record_is_kept(make_municipality):
    import datetime

    from apps.properties.models import Property
    from apps.reports.models import Report, ReportStatus
    from compliance import retention
    from django.utils import timezone

    municipality = make_municipality(name="Provenance town")
    record = Property.objects.create(organization=municipality.organization, city="Town")
    report = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        status=ReportStatus.REJECTED,
        property=record,
    )
    Report.objects.filter(pk=report.pk).update(
        updated_at=timezone.now() - datetime.timedelta(days=400)
    )
    # It is part of the record's provenance, so it stays.
    assert retention.purge_discarded_reports() == 0
    assert Report.objects.filter(pk=report.pk).exists()


@pytest.mark.django_db
def test_submitting_addresses_are_dropped_once_they_serve_no_purpose(make_municipality):
    import datetime

    from apps.reports.models import Report
    from compliance import retention
    from django.utils import timezone

    municipality = make_municipality(name="Origin town")
    old = Report.objects.create(
        organization=municipality.organization, city="Town", submitted_from_ip="203.0.113.9"
    )
    recent = Report.objects.create(
        organization=municipality.organization, city="Town", submitted_from_ip="203.0.113.10"
    )
    Report.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=90)
    )

    assert retention.anonymise_report_origins() == 1
    old.refresh_from_db()
    recent.refresh_from_db()
    assert old.submitted_from_ip is None
    assert recent.submitted_from_ip == "203.0.113.10"


@pytest.mark.django_db
def test_contact_details_nobody_asked_us_to_keep_are_stripped(make_municipality):
    from apps.reports.models import Report, ReportStatus
    from compliance import retention

    municipality = make_municipality(name="Contact town")
    declined = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        status=ReportStatus.ACCEPTED,
        wants_feedback=False,
        contact_email="anna@example.com",
        contact_name="Anna",
    )
    wanted = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        status=ReportStatus.ACCEPTED,
        wants_feedback=True,
        contact_email="bob@example.com",
    )
    open_report = Report.objects.create(
        organization=municipality.organization,
        city="Town",
        status=ReportStatus.SUBMITTED,
        contact_email="carla@example.com",
    )

    retention.strip_contact_details_of_declined_feedback()
    declined.refresh_from_db()
    wanted.refresh_from_db()
    open_report.refresh_from_db()
    assert declined.contact_email == ""
    assert declined.contact_name == ""
    # Somebody who asked to hear back keeps their address.
    assert wanted.contact_email == "bob@example.com"
    # And a report still being moderated is left alone.
    assert open_report.contact_email == "carla@example.com"


@pytest.mark.django_db
def test_the_access_log_is_itself_subject_to_retention(make_municipality):
    import datetime

    from compliance import retention
    from compliance.audit import log_access
    from compliance.models import AccessCategory, AccessLog
    from django.utils import timezone

    municipality = make_municipality(name="Log town")
    entry = log_access(
        None, AccessCategory.OWNER_DATA, organization=municipality.organization
    )
    AccessLog.objects.filter(pk=entry.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=1000)
    )
    assert retention.purge_access_log() == 1
    assert AccessLog.objects.count() == 0


@pytest.mark.django_db
def test_the_retention_command_reports_what_it_did(make_municipality, capsys):
    from django.core.management import call_command

    make_municipality(name="Command town")
    call_command("apply_retention")
    output = capsys.readouterr().out
    assert "discarded_reports_deleted" in output
    assert "report_origins_anonymised" in output


@pytest.mark.django_db
def test_the_retention_command_can_be_run_dry(make_municipality, capsys):
    import datetime

    from apps.reports.models import Report, ReportStatus
    from django.core.management import call_command
    from django.utils import timezone

    municipality = make_municipality(name="Dry town")
    report = Report.objects.create(
        organization=municipality.organization, city="Town", status=ReportStatus.SPAM
    )
    Report.objects.filter(pk=report.pk).update(
        updated_at=timezone.now() - datetime.timedelta(days=400)
    )
    call_command("apply_retention", "--dry-run")
    assert "dry run" in capsys.readouterr().out
    # Nothing was actually removed.
    assert Report.objects.filter(pk=report.pk).exists()
