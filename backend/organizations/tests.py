import pytest
from django.core import mail
from django.urls import reverse

from organizations.models import (
    INTERNAL_ROLES,
    STAFF_ROLES,
    Invitation,
    Organization,
    Role,
)


@pytest.mark.django_db
def test_signup_does_not_create_a_tenant(make_user):
    """Citizens sign up without becoming the owner of a municipality."""
    user = make_user(username="zoe")
    assert user.organizations.count() == 0


@pytest.mark.django_db
def test_tenant_creation_is_reserved_for_the_instance_operator(client, make_user):
    citizen = make_user(username="citizen")
    client.force_login(citizen)
    assert client.post(reverse("organizations:create"), {"name": "Acme"}).status_code == 403

    operator = make_user(username="operator", is_staff=True)
    client.force_login(operator)
    response = client.post(reverse("organizations:create"), {"name": "Reichenbach"})
    assert response.status_code == 302
    org = Organization.objects.get(name="Reichenbach")
    assert org.get_role(operator) == Role.OWNER
    assert client.session["active_organization_id"] == org.pk


@pytest.mark.django_db
def test_detail_visible_to_member_only(client, make_member, make_user):
    owner, org = make_member(username="owner1")
    other = make_user(username="other1")

    client.force_login(other)
    assert client.get(org.get_absolute_url()).status_code == 404

    client.force_login(owner)
    assert client.get(org.get_absolute_url()).status_code == 200


@pytest.mark.django_db
def test_manager_can_invite_sends_email(client, make_member):
    owner, org = make_member(username="owner2")
    client.force_login(owner)
    mail.outbox.clear()
    response = client.post(
        reverse("organizations:invite", args=[org.slug]),
        {"email": "new@example.com", "role": Role.MEMBER.value},
    )
    assert response.status_code == 302
    assert Invitation.objects.filter(organization=org, email="new@example.com").exists()
    assert any("invited" in m.subject.lower() for m in mail.outbox)


@pytest.mark.django_db
def test_member_cannot_invite(client, make_member):
    _owner, org = make_member(username="owner3")
    member, _ = make_member(role=Role.MEMBER, organization=org, username="member3")
    client.force_login(member)
    response = client.post(
        reverse("organizations:invite", args=[org.slug]),
        {"email": "x@example.com", "role": Role.MEMBER.value},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_accept_invitation_creates_membership(client, make_member, make_user):
    _owner, org = make_member(username="owner4")
    invitee = make_user(username="invitee4")
    invitation = Invitation.objects.create(
        organization=org, email="invitee4@example.com", role=Role.BUILDING_AUTHORITY
    )
    client.force_login(invitee)
    response = client.post(invitation.get_accept_url())
    assert response.status_code == 302
    assert org.get_role(invitee) == Role.BUILDING_AUTHORITY
    invitation.refresh_from_db()
    assert invitation.is_accepted


@pytest.mark.django_db
def test_switch_organization_sets_session(client, make_member, make_tenant):
    user, _first = make_member(username="switch1")
    second = make_tenant(name="Second")
    second.add_member(user, role=Role.OWNER)
    client.force_login(user)
    response = client.post(reverse("organizations:switch", args=[second.pk]))
    assert response.status_code == 302
    assert client.session["active_organization_id"] == second.pk


@pytest.mark.django_db
def test_cannot_remove_last_owner(client, make_member):
    owner, org = make_member(username="owner5")
    membership = org.memberships.get(user=owner)
    client.force_login(owner)
    response = client.post(reverse("organizations:remove_member", args=[org.slug, membership.pk]))
    assert response.status_code == 302
    assert org.memberships.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_department_roles_grant_internal_but_not_manage_rights(make_member):
    staff, org = make_member(role=Role.BUILDING_AUTHORITY, username="bauamt")
    assert org.has_internal_access(staff)
    assert org.is_staff_member(staff)
    assert org.can_verify(staff)
    assert not org.can_manage(staff)


@pytest.mark.django_db
def test_verified_contributor_may_verify_but_is_not_staff(make_member):
    contributor, org = make_member(role=Role.VERIFIED_CONTRIBUTOR, username="helper")
    assert org.can_verify(contributor)
    assert not org.is_staff_member(contributor)
    assert not org.has_internal_access(contributor)


@pytest.mark.django_db
def test_external_agency_reads_without_editing(make_member):
    agency, org = make_member(role=Role.EXTERNAL_AGENCY, username="landkreis")
    assert org.has_internal_access(agency)
    assert not org.is_staff_member(agency)
    assert not org.can_verify(agency)


def test_role_sets_are_consistent():
    """Every editing role also grants access to the administration area."""
    assert STAFF_ROLES.issubset(INTERNAL_ROLES)
    assert Role.OWNER in STAFF_ROLES
    assert Role.VERIFIED_CONTRIBUTOR not in INTERNAL_ROLES
