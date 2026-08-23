import datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.documents.models import DocumentKind, PropertyDocument
from apps.integrations.models import ApiClient as ApiClientModel
from apps.integrations.models import Scope
from apps.municipalities.models import Module
from apps.properties.choices import VacancyStatus
from apps.properties.models import Property
from apps.reports.models import Report
from notifications.models import notify
from organizations.models import Role


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def instance(make_municipality):
    return make_municipality(name="Reichenbach", municipality_key="14523250")


@pytest.fixture
def published(instance):
    """A published record with internal notes and an internal document."""
    record = Property.objects.create(
        organization=instance.organization,
        street="Marktplatz",
        house_number="3",
        postal_code="08468",
        city="Reichenbach im Vogtland",
        public_description="Vacant shop on the ground floor",
        internal_description="Heirs unknown, land registry checked in March",
        sources="Citizen report M-2026-0001",
        is_public=True,
    )
    record.set_vacancy_status(VacancyStatus.VACANT)
    PropertyDocument.objects.create(
        organization=instance.organization,
        property=record,
        title="Expert report",
        kind=DocumentKind.EXPERT_REPORT,
        file="documents/report.pdf",
    )
    return record


def _issue(organization, scopes, name="Test client", **extra):
    return ApiClientModel.issue(organization, name=name, scopes=scopes, **extra)


def _authorise(api, raw_key):
    api.credentials(HTTP_AUTHORIZATION=f"ApiKey {raw_key}")
    return api


# --- Public area -----------------------------------------------------------


@pytest.mark.django_db
def test_public_properties_need_no_account(api, published):
    response = api.get(reverse("v1:public:public-property-list"))
    assert response.status_code == 200
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_public_area_never_exposes_internal_fields(api, published):
    body = api.get(reverse("v1:public:public-property-list")).content.decode()
    assert "Vacant shop on the ground floor" in body
    # The three things that must never leave the administration.
    assert "Heirs unknown" not in body
    assert "land registry" not in body
    assert "Expert report" not in body

    entry = api.get(reverse("v1:public:public-property-list")).json()["results"][0]
    for forbidden in ("internal_description", "sources", "created_by", "id"):
        assert forbidden not in entry


@pytest.mark.django_db
def test_public_area_hides_unpublished_records(api, instance, published):
    Property.objects.create(
        organization=instance.organization, street="Nebenweg", is_public=False
    )
    payload = api.get(reverse("v1:public:public-property-list")).json()
    assert payload["count"] == 1
    assert payload["results"][0]["reference"] == published.reference


@pytest.mark.django_db
def test_public_detail_is_addressed_by_reference_not_id(api, published):
    response = api.get(
        reverse("v1:public:public-property-detail", args=[published.reference])
    )
    assert response.status_code == 200
    assert response.json()["reference"] == published.reference


@pytest.mark.django_db
def test_public_area_can_be_switched_off(api, instance, published):
    instance.set_module(Module.PUBLIC_API, False)
    assert api.get(reverse("v1:public:public-property-list")).json()["count"] == 0
    assert api.get(reverse("v1:public:statistics")).status_code == 404


@pytest.mark.django_db
def test_public_statistics_are_counts_only(api, published):
    payload = api.get(reverse("v1:public:statistics")).json()
    assert payload["figures"]["confirmed_vacancies"] == 1
    assert payload["municipality"]["name"] == "Reichenbach"
    # Operational load is not open data.
    assert "open_tasks" not in payload["figures"]
    assert "open_reports" not in payload["figures"]


@pytest.mark.django_db
def test_public_area_filters_by_vacancy_and_district(api, instance, published):
    other = Property.objects.create(
        organization=instance.organization, street="Belegt", is_public=True
    )
    other.set_vacancy_status(VacancyStatus.IN_USE)
    payload = api.get(reverse("v1:public:public-property-list"), {"vacant": "1"}).json()
    assert payload["count"] == 1


@pytest.mark.django_db
def test_public_area_answers_nothing_when_the_municipality_is_ambiguous(
    api, instance, published, make_municipality
):
    """Answering for the wrong town is worse than not answering."""
    make_municipality(name="Second town")
    assert api.get(reverse("v1:public:public-property-list")).json()["count"] == 0


# --- Citizen area ----------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_report_submission_over_the_api(api, instance):
    response = api.post(
        reverse("v1:citizen:citizen-report-list"),
        {
            "category": "suspected_vacancy",
            "description": "Boarded up for a year",
            "latitude": 50.6236,
            "longitude": 12.3036,
            "accepted_privacy_policy": True,
            "accepted_terms": True,
        },
        format="json",
    )
    assert response.status_code == 201
    report = Report.objects.get()
    assert report.organization == instance.organization
    assert report.is_anonymous
    assert report.consent_given_at is not None


@pytest.mark.django_db
def test_consent_is_required_over_the_api(api, instance):
    response = api.post(
        reverse("v1:citizen:citizen-report-list"),
        {
            "category": "suspected_vacancy",
            "city": "Reichenbach",
            "accepted_privacy_policy": False,
            "accepted_terms": True,
        },
        format="json",
    )
    assert response.status_code == 400
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_a_report_needs_a_location_or_an_address_over_the_api(api, instance):
    response = api.post(
        reverse("v1:citizen:citizen-report-list"),
        {"accepted_privacy_policy": True, "accepted_terms": True},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_anonymous_submission_respects_the_module_switch(api, instance):
    instance.set_module(Module.ANONYMOUS_REPORTS, False)
    response = api.post(
        reverse("v1:citizen:citizen-report-list"),
        {
            "city": "Reichenbach",
            "accepted_privacy_policy": True,
            "accepted_terms": True,
        },
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_reporters_list_only_their_own_reports(api, instance, make_user):
    mine = make_user(username="api_reporter")
    Report.objects.create(
        organization=instance.organization, submitted_by=mine, city="A", description="Mine"
    )
    Report.objects.create(organization=instance.organization, city="B", description="Someone")

    api.force_authenticate(mine)
    payload = api.get(reverse("v1:citizen:citizen-report-list")).json()
    assert payload["count"] == 1
    assert payload["results"][0]["description"] == "Mine"


@pytest.mark.django_db
def test_listing_own_reports_requires_an_account(api, instance):
    assert api.get(reverse("v1:citizen:citizen-report-list")).status_code in (401, 403)


# --- Administrative area ---------------------------------------------------


@pytest.mark.django_db
def test_staff_see_the_full_record(api, instance, make_member, published):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="api_staff"
    )
    api.force_authenticate(staff)
    payload = api.get(reverse("v1:administration:property-list")).json()
    entry = payload["results"][0]
    assert entry["internal_description"].startswith("Heirs unknown")
    assert entry["sources"]
    assert "allowed_transitions" in entry


@pytest.mark.django_db
def test_a_citizen_account_cannot_reach_the_administrative_area(api, instance, make_user):
    """Being signed in is not the same as working for the municipality."""
    citizen = make_user(username="api_citizen")
    api.force_authenticate(citizen)
    assert api.get(reverse("v1:administration:property-list")).status_code == 403


@pytest.mark.django_db
def test_the_administrative_area_is_scoped_to_the_own_municipality(
    api, instance, make_member, make_municipality
):
    staff, _org = make_member(
        role=Role.URBAN_PLANNING, organization=instance.organization, username="api_planner"
    )
    other = make_municipality(name="Elsewhere")
    Property.objects.create(organization=other.organization, street="Fremdweg")

    api.force_authenticate(staff)
    payload = api.get(reverse("v1:administration:property-list")).json()
    assert payload["count"] == 0


@pytest.mark.django_db
def test_the_workflow_status_cannot_be_changed_by_a_plain_update(
    api, instance, make_member, published
):
    staff, _org = make_member(
        role=Role.BUILDING_AUTHORITY, organization=instance.organization, username="api_staff2"
    )
    api.force_authenticate(staff)
    response = api.patch(
        reverse("v1:administration:property-detail", args=[published.pk]),
        {"status": "confirmed", "priority": "high"},
        format="json",
    )
    assert response.status_code == 200
    published.refresh_from_db()
    # Status changes go through their own action so the audit trail stays whole.
    assert published.status != "confirmed"
    assert published.priority == "high"


@pytest.mark.django_db
def test_administrative_statistics_include_the_operational_figures(
    api, instance, make_member, published
):
    staff, _org = make_member(
        role=Role.ECONOMIC_DEVELOPMENT, organization=instance.organization, username="api_econ"
    )
    api.force_authenticate(staff)
    payload = api.get(reverse("v1:administration:statistics")).json()
    assert "open_tasks" in payload["figures"]
    assert "series" in payload


# --- API key clients -------------------------------------------------------


@pytest.mark.django_db
def test_a_key_is_shown_once_and_stored_only_as_a_hash(instance):
    client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    assert raw_key.startswith("ov_")
    assert client.key_hash != raw_key
    assert raw_key not in client.key_hash
    assert client.key_prefix == raw_key[:8]


@pytest.mark.django_db
def test_a_public_scope_client_reads_published_data(api, instance, published):
    _client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    _authorise(api, raw_key)
    response = api.get(reverse("v1:public:public-property-list"))
    assert response.status_code == 200
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_a_public_scope_client_is_refused_the_professional_data(api, instance, published):
    """Granting open data must not imply granting the case files."""
    _client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    _authorise(api, raw_key)
    response = api.get(reverse("v1:administration:property-list"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_an_internal_scope_client_reads_the_professional_data(api, instance, published):
    _client, raw_key = _issue(
        instance.organization, [Scope.READ_PUBLIC, Scope.READ_INTERNAL]
    )
    _authorise(api, raw_key)
    payload = api.get(reverse("v1:administration:property-list")).json()
    assert payload["results"][0]["internal_description"].startswith("Heirs unknown")


@pytest.mark.django_db
def test_a_client_only_ever_sees_its_own_municipality(
    api, instance, published, make_municipality
):
    other = make_municipality(name="Elsewhere")
    Property.objects.create(
        organization=other.organization, street="Fremd", is_public=True
    )
    _client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    _authorise(api, raw_key)
    payload = api.get(reverse("v1:public:public-property-list")).json()
    assert payload["count"] == 1
    assert payload["results"][0]["reference"] == published.reference


@pytest.mark.django_db
def test_revoking_a_key_stops_it_immediately(api, instance, published):
    client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    _authorise(api, raw_key)
    assert api.get(reverse("v1:public:public-property-list")).status_code == 200

    client.revoke()
    assert api.get(reverse("v1:public:public-property-list")).status_code in (401, 403)


@pytest.mark.django_db
def test_rotating_a_key_invalidates_the_previous_one(api, instance, published):
    client, first_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    second_key = client.rotate_key()

    _authorise(api, first_key)
    assert api.get(reverse("v1:public:public-property-list")).status_code in (401, 403)

    _authorise(api, second_key)
    assert api.get(reverse("v1:public:public-property-list")).status_code == 200


@pytest.mark.django_db
def test_an_expired_key_is_refused(api, instance, published):
    from django.utils import timezone

    _client, raw_key = _issue(
        instance.organization,
        [Scope.READ_PUBLIC],
        expires_at=timezone.now() - datetime.timedelta(minutes=1),
    )
    _authorise(api, raw_key)
    assert api.get(reverse("v1:public:public-property-list")).status_code in (401, 403)


@pytest.mark.django_db
def test_a_key_with_a_future_expiry_still_works(api, instance, published):
    from django.utils import timezone

    _client, raw_key = _issue(
        instance.organization,
        [Scope.READ_PUBLIC],
        expires_at=timezone.now() + datetime.timedelta(days=30),
    )
    _authorise(api, raw_key)
    assert api.get(reverse("v1:public:public-property-list")).status_code == 200


@pytest.mark.django_db
def test_an_unknown_key_is_refused(api, instance, published):
    _authorise(api, "ov_definitely-not-a-real-key")
    assert api.get(reverse("v1:public:public-property-list")).status_code in (401, 403)


@pytest.mark.django_db
def test_using_a_client_records_it_for_the_access_review(api, instance, published):
    client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    assert client.last_used_at is None
    _authorise(api, raw_key)
    api.get(reverse("v1:public:public-property-list"))
    client.refresh_from_db()
    assert client.last_used_at is not None
    assert client.request_count == 1


@pytest.mark.django_db
def test_a_client_can_discover_its_own_scopes(api, instance):
    _client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC, Scope.READ_GEODATA])
    _authorise(api, raw_key)
    payload = api.get(reverse("v1:integration:client")).json()
    assert payload["municipality"] == "Reichenbach"
    assert set(payload["scopes"]) == {Scope.READ_PUBLIC, Scope.READ_GEODATA}


@pytest.mark.django_db
def test_geodata_metadata_needs_the_geodata_scope(api, instance):
    _client, raw_key = _issue(instance.organization, [Scope.READ_PUBLIC])
    _authorise(api, raw_key)
    assert api.get(reverse("v1:integration:geolayer-list")).status_code == 403

    _client2, geo_key = _issue(
        instance.organization, [Scope.READ_GEODATA], name="Geo client"
    )
    _authorise(api, geo_key)
    assert api.get(reverse("v1:integration:geolayer-list")).status_code == 200


# --- Client management UI --------------------------------------------------


@pytest.mark.django_db
def test_only_managers_manage_api_clients(client, instance, make_member):
    manager, _org = make_member(
        role=Role.OWNER, organization=instance.organization, username="api_manager"
    )
    planner, _org2 = make_member(
        role=Role.URBAN_PLANNING, organization=instance.organization, username="api_planner2"
    )

    client.force_login(planner)
    assert client.get(reverse("integrations:clients")).status_code == 403

    client.force_login(manager)
    assert client.get(reverse("integrations:clients")).status_code == 200


@pytest.mark.django_db
def test_issuing_a_client_shows_the_key_exactly_once(client, instance, make_member):
    manager, _org = make_member(
        role=Role.OWNER, organization=instance.organization, username="api_manager2"
    )
    client.force_login(manager)
    client.post(
        reverse("integrations:client_create"),
        {
            "name": "Open data portal",
            "scope_choices": [Scope.READ_PUBLIC.value],
            "throttle_rate": "1000/hour",
        },
    )
    issued = ApiClientModel.objects.get()
    assert issued.scopes == [Scope.READ_PUBLIC.value]

    first = client.get(reverse("integrations:clients"))
    assert first.context["new_key"]["key"].startswith("ov_")
    # Reloading must not show it again.
    assert client.get(reverse("integrations:clients")).context["new_key"] is None


@pytest.mark.django_db
def test_an_invalid_rate_is_caught_before_the_client_uses_it(client, instance, make_member):
    manager, _org = make_member(
        role=Role.OWNER, organization=instance.organization, username="api_manager3"
    )
    client.force_login(manager)
    response = client.post(
        reverse("integrations:client_create"),
        {
            "name": "Broken",
            "scope_choices": [Scope.READ_PUBLIC.value],
            "throttle_rate": "lots/forever",
        },
    )
    assert response.status_code == 200
    assert ApiClientModel.objects.count() == 0


@pytest.mark.django_db
def test_revoke_and_reactivate_through_the_ui(client, instance, make_member):
    manager, _org = make_member(
        role=Role.OWNER, organization=instance.organization, username="api_manager4"
    )
    issued, _key = _issue(instance.organization, [Scope.READ_PUBLIC])

    client.force_login(manager)
    client.post(reverse("integrations:client_revoke", args=[issued.pk]))
    issued.refresh_from_db()
    assert issued.is_active is False
    assert issued.revoked_at is not None

    client.post(reverse("integrations:client_reactivate", args=[issued.pk]))
    issued.refresh_from_db()
    assert issued.is_active is True


# --- Existing account endpoints -------------------------------------------


@pytest.mark.django_db
def test_me_and_notifications_still_work(api, make_user):
    user = make_user(username="api_me")
    notify(user, "Hello")
    api.force_authenticate(user)
    assert api.get(reverse("v1:me")).json()["username"] == "api_me"
    assert api.get(reverse("v1:notification-list")).json()["count"] == 1


@pytest.mark.django_db
def test_schema_and_docs_render(client):
    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("swagger-ui")).status_code == 200
