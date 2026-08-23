from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.response import Response

from api.serializers import (
    NotificationSerializer,
    OrganizationSerializer,
    UserSerializer,
)


def current_organization(request):
    """Resolve the active org for both session (middleware) and token clients."""
    org = getattr(request, "organization", None)
    if org is None and request.user.is_authenticated:
        org = request.user.organizations.first()
    return org


class MeView(RetrieveUpdateAPIView):
    """Get or update the authenticated user's profile."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class OrganizationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = OrganizationSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return self.request.user.organizations.all()


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return self.request.user.notifications.all()

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.unread = False
        notification.save(update_fields=["unread"])
        return Response({"status": "read"})
