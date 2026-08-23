import datetime

import pytest

from apps.funding.models import ApplicationStatus, FundingProgramme, PropertyFunding
from apps.properties.models import Property


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="funding_staff")
    record = Property.objects.create(organization=organization, street="Fördergasse")
    return user, organization, municipality, record


@pytest.mark.django_db
def test_a_programme_is_open_only_within_its_window(setup):
    _user, organization, _municipality, _record = setup
    today = datetime.date.today()

    open_now = FundingProgramme.objects.create(
        organization=organization,
        name="Town centre renewal",
        starts_on=today - datetime.timedelta(days=10),
        ends_on=today + datetime.timedelta(days=10),
    )
    assert open_now.is_open is True

    future = FundingProgramme.objects.create(
        organization=organization,
        name="Next year",
        starts_on=today + datetime.timedelta(days=30),
    )
    assert future.is_open is False

    expired = FundingProgramme.objects.create(
        organization=organization,
        name="Last year",
        ends_on=today - datetime.timedelta(days=1),
    )
    assert expired.is_open is False

    inactive = FundingProgramme.objects.create(
        organization=organization, name="Suspended", is_active=False
    )
    assert inactive.is_open is False


@pytest.mark.django_db
def test_a_programme_without_dates_is_open(setup):
    _user, organization, _municipality, _record = setup
    programme = FundingProgramme.objects.create(organization=organization, name="Ongoing")
    assert programme.is_open is True


@pytest.mark.django_db
def test_progress_is_tracked_once_per_object_and_programme(setup):
    from django.db import IntegrityError

    _user, organization, _municipality, record = setup
    programme = FundingProgramme.objects.create(organization=organization, name="Programme")
    PropertyFunding.objects.create(
        organization=organization, property=record, programme=programme
    )
    with pytest.raises(IntegrityError):
        PropertyFunding.objects.create(
            organization=organization, property=record, programme=programme
        )


@pytest.mark.django_db
def test_funding_progress_defaults_to_only_possible(setup):
    """Eligibility is a judgement, so nothing starts out as established."""
    _user, organization, _municipality, record = setup
    programme = FundingProgramme.objects.create(organization=organization, name="Programme")
    funding = PropertyFunding.objects.create(
        organization=organization, property=record, programme=programme
    )
    assert funding.status == ApplicationStatus.POSSIBLE


@pytest.mark.django_db
def test_required_layers_are_stored_as_keys(setup):
    """Keys rather than foreign keys, so a re-imported layer does not break it."""
    _user, organization, _municipality, _record = setup
    programme = FundingProgramme.objects.create(
        organization=organization,
        name="Redevelopment area programme",
        required_layer_slugs=["redevelopment-areas"],
    )
    assert programme.required_layer_slugs == ["redevelopment-areas"]
