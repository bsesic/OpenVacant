import pytest

from apps.federation.models import (
    DataCategory,
    Direction,
    PeerInstance,
    ShareScope,
    SyncRun,
    SyncStatus,
)


@pytest.fixture
def peer(municipal_staff):
    _user, organization, _municipality = municipal_staff(username="fed_staff")
    return PeerInstance.objects.create(
        organization=organization,
        name="Vogtlandkreis",
        level="district",
        base_url="https://vogtlandkreis.example/api/v1/",
    )


@pytest.mark.django_db
def test_a_peer_shares_nothing_by_default(peer):
    """Nothing leaves an instance unless somebody said so."""
    assert peer.is_active is False
    assert peer.enabled_categories == set()
    assert peer.shares(DataCategory.PUBLISHED_RECORDS) is False


@pytest.mark.django_db
def test_sharing_is_per_category_and_direction(peer):
    peer.is_active = True
    peer.save(update_fields=["is_active"])
    ShareScope.objects.create(
        peer=peer,
        category=DataCategory.AGGREGATE_STATISTICS,
        direction=Direction.OUTBOUND,
        is_enabled=True,
    )

    assert peer.shares(DataCategory.AGGREGATE_STATISTICS) is True
    # Granting one category must not imply another.
    assert peer.shares(DataCategory.PUBLISHED_RECORDS) is False
    # Nor the other direction.
    assert (
        peer.shares(DataCategory.AGGREGATE_STATISTICS, direction=Direction.INBOUND) is False
    )


@pytest.mark.django_db
def test_deactivating_a_peer_stops_all_sharing(peer):
    peer.is_active = True
    peer.save(update_fields=["is_active"])
    ShareScope.objects.create(
        peer=peer,
        category=DataCategory.PUBLISHED_RECORDS,
        direction=Direction.OUTBOUND,
        is_enabled=True,
    )
    assert peer.shares(DataCategory.PUBLISHED_RECORDS) is True

    peer.is_active = False
    peer.save(update_fields=["is_active"])
    assert peer.shares(DataCategory.PUBLISHED_RECORDS) is False


@pytest.mark.django_db
def test_a_disabled_scope_does_not_share(peer):
    peer.is_active = True
    peer.save(update_fields=["is_active"])
    ShareScope.objects.create(
        peer=peer,
        category=DataCategory.PUBLISHED_RECORDS,
        direction=Direction.OUTBOUND,
        is_enabled=False,
    )
    assert peer.shares(DataCategory.PUBLISHED_RECORDS) is False


@pytest.mark.django_db
def test_only_one_scope_per_peer_category_and_direction(peer):
    from django.db import IntegrityError

    ShareScope.objects.create(
        peer=peer, category=DataCategory.PUBLISHED_RECORDS, direction=Direction.OUTBOUND
    )
    with pytest.raises(IntegrityError):
        ShareScope.objects.create(
            peer=peer, category=DataCategory.PUBLISHED_RECORDS, direction=Direction.OUTBOUND
        )


@pytest.mark.django_db
def test_there_is_no_category_for_personal_or_internal_data():
    """Owner details and internal notes are not shareable at all."""
    categories = {choice.value for choice in DataCategory}
    for forbidden in ("owners", "internal_notes", "contacts", "documents"):
        assert forbidden not in categories


@pytest.mark.django_db
def test_a_run_records_the_outcome(peer):
    run = SyncRun.objects.create(
        peer=peer, direction=Direction.OUTBOUND, category=DataCategory.PUBLISHED_RECORDS
    )
    assert run.status == SyncStatus.RUNNING
    run.finish(SyncStatus.SUCCEEDED, record_count=42, message="ok")
    assert run.status == SyncStatus.SUCCEEDED
    assert run.record_count == 42
    assert run.finished_at is not None


@pytest.mark.django_db
def test_a_refusal_by_the_peer_is_recorded_as_such(peer):
    run = SyncRun.objects.create(
        peer=peer, direction=Direction.INBOUND, category=DataCategory.INCOMING_REPORTS
    )
    run.finish(SyncStatus.REFUSED, message="Peer declined the category")
    assert run.status == SyncStatus.REFUSED
