"""Shared pytest fixtures for the OpenVacant test suite."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the cache between tests so rate-limit counters don't leak."""
    cache.clear()
    yield


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Run Celery tasks inline so no test ever needs a broker or a worker.

    Celery reads its configuration lazily through ``django.conf:settings``, so the
    Django setting is the only override that takes effect — assigning to
    ``app.conf`` is silently overridden on the next read.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def make_user(db):
    """Factory fixture that creates users with unique usernames/emails.

    A plain user is a citizen: signing up neither creates nor joins a tenant.
    """
    counter = {"n": 0}

    def _make(username=None, password="testpass123", **extra):
        counter["n"] += 1
        n = counter["n"]
        return User.objects.create_user(
            username=username or f"user{n}",
            email=extra.pop("email", f"user{n}@example.com"),
            password=password,
            **extra,
        )

    return _make


@pytest.fixture
def make_tenant(db):
    """Factory for bare tenants, without a municipality profile."""
    from organizations.models import Organization

    counter = {"n": 0}

    def _make(name=None):
        counter["n"] += 1
        return Organization.objects.create(name=name or f"Tenant {counter['n']}")

    return _make


@pytest.fixture
def make_member(make_user, make_tenant):
    """Create a user holding ``role`` in a tenant, creating the tenant if needed."""
    from organizations.models import Role

    def _make(role=Role.OWNER, organization=None, username=None, **extra):
        organization = organization or make_tenant()
        user = make_user(username=username, **extra)
        organization.add_member(user, role=role)
        return user, organization

    return _make
