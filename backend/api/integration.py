"""Integration API.

For external systems: geodata layers, and the client's own view of what it may
do. Kept apart from the administrative area because these are the endpoints an
integration needs to orient itself, not the professional case data.
"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.resolution import api_organization
from apps.geodata.models import GeoLayer
from apps.integrations.authentication import HasApiScope


class GeoLayerSerializer(serializers.ModelSerializer):
    feature_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = GeoLayer
        fields = (
            "slug",
            "name",
            "category",
            "description",
            "source",
            "source_url",
            "licence",
            "is_public",
            "feature_count",
            "imported_at",
        )
        read_only_fields = fields


@extend_schema(tags=["integration"])
class GeoLayerViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Which layers this municipality holds.

    A client with the geodata scope sees the metadata of all active layers; a
    caller without it sees only the layers the municipality marked public.
    """

    serializer_class = GeoLayerSerializer
    permission_classes = [IsAuthenticated, HasApiScope]
    required_scope = "read_geodata"
    lookup_field = "slug"

    def get_queryset(self):
        organization = api_organization(self.request)
        if organization is None:
            return GeoLayer.objects.none()
        return GeoLayer.objects.for_organization(organization).filter(is_active=True)


class ApiClientSelfSerializer(serializers.Serializer):
    """What a client is told about itself."""

    name = serializers.CharField()
    municipality = serializers.CharField()
    scopes = serializers.ListField(child=serializers.CharField())
    expires_at = serializers.DateTimeField(allow_null=True)
    rate_limit = serializers.CharField()


@extend_schema(tags=["integration"], responses=ApiClientSelfSerializer)
class ApiClientSelfView(APIView):
    """What the calling client is and what it may do.

    An integration should be able to discover its own scopes rather than
    discovering them from a sequence of 403s.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ApiClientSelfSerializer

    def get(self, request):
        client = getattr(request, "api_client", None)
        if client is None:
            return Response(
                {"detail": _("This endpoint is for API key clients.")}, status=400
            )
        return Response(
            {
                "name": client.name,
                "municipality": client.organization.municipality.name,
                "scopes": client.scopes,
                "expires_at": client.expires_at,
                "rate_limit": client.throttle_rate,
            }
        )
