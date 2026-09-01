import pytest

from apps.owners.models import (
    ClaimStatus,
    ContactState,
    InterestKind,
    Owner,
    OwnerInterest,
    Ownership,
    OwnershipClaim,
)
from apps.properties.models import Property


@pytest.fixture
def setup(municipal_staff):
    user, organization, municipality = municipal_staff(username="owners_staff")
    record = Property.objects.create(organization=organization, street="Erbenweg")
    return user, organization, municipality, record


@pytest.mark.django_db
def test_an_owner_can_be_recorded_without_contact_details(setup):
    """"Owner unknown" is a real state the administration needs to record."""
    _user, organization, _municipality, _record = setup
    owner = Owner.objects.create(organization=organization)
    assert owner.contact_state == ContactState.UNKNOWN
    assert owner.is_reachable is False

    owner.contact_state = ContactState.IN_DIALOGUE
    assert owner.is_reachable is True


@pytest.mark.django_db
def test_ownership_can_be_divided_among_heirs(setup):
    _user, organization, _municipality, record = setup
    heirs = Owner.objects.create(
        organization=organization,
        name="Community of heirs Müller",
        kind="community_of_heirs",
        representative="Anna Müller",
    )
    Ownership.objects.create(
        organization=organization, property=record, owner=heirs, share="1/3"
    )
    assert record.ownerships.count() == 1
    assert record.ownerships.get().share == "1/3"


@pytest.mark.django_db
def test_a_claim_grants_nothing_until_it_is_reviewed(setup, make_user):
    """A self-verifying claim would let a stranger speak for a building."""
    _user, organization, _municipality, record = setup
    claimant = make_user(username="claims_to_own")
    claim = OwnershipClaim.objects.create(
        organization=organization,
        property=record,
        claimant=claimant,
        evidence_note="Purchase contract from 2019",
    )
    assert claim.status == ClaimStatus.PENDING
    assert claim.is_effective is False

    claim.review(ClaimStatus.VERIFIED, actor=_user, note="Contract seen")
    assert claim.is_effective is True
    assert claim.reviewed_by == _user
    assert claim.reviewed_at is not None


@pytest.mark.django_db
def test_a_rejected_claim_stays_ineffective(setup, make_user):
    _user, organization, _municipality, record = setup
    claimant = make_user(username="rejected_claim")
    claim = OwnershipClaim.objects.create(
        organization=organization, property=record, claimant=claimant
    )
    claim.review(ClaimStatus.REJECTED, actor=_user)
    assert claim.is_effective is False


@pytest.mark.django_db
def test_only_one_open_claim_per_person_and_object(setup, make_user):
    from django.db import IntegrityError

    _user, organization, _municipality, record = setup
    claimant = make_user(username="repeat_claimer")
    OwnershipClaim.objects.create(
        organization=organization, property=record, claimant=claimant
    )
    with pytest.raises(IntegrityError):
        OwnershipClaim.objects.create(
            organization=organization, property=record, claimant=claimant
        )


@pytest.mark.django_db
def test_owner_interest_is_recorded_per_statement(setup):
    _user, organization, _municipality, record = setup
    owner = Owner.objects.create(organization=organization, name="Owner")
    OwnerInterest.objects.create(
        organization=organization,
        property=record,
        owner=owner,
        kind=InterestKind.SUPPORT_NEEDED,
        note="Would renovate with help",
    )
    OwnerInterest.objects.create(
        organization=organization, property=record, owner=owner, kind=InterestKind.SELL
    )
    # Both statements are kept; a later one does not erase an earlier one.
    assert record.owner_interests.count() == 2


@pytest.mark.django_db
def test_owner_data_is_scoped_to_the_municipality(setup, make_municipality):
    _user, organization, _municipality, _record = setup
    other = make_municipality(name="Elsewhere")
    Owner.objects.create(organization=organization, name="Ours")
    Owner.objects.create(organization=other.organization, name="Theirs")

    assert Owner.objects.for_organization(organization).count() == 1
    assert Owner.objects.for_organization(organization).get().name == "Ours"
