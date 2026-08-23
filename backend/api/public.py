"""Public API.

Open data: what a municipality has decided to publish, and nothing else. Every
serializer here is written from scratch rather than inherited from an
administrative one, so a field cannot arrive by inheritance. See ADR 0009.
"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.resolution import api_organization
from apps.documents.models import DocumentKind
from apps.integrations.authentication import HasApiScope
from apps.municipalities.models import Module
from apps.properties.models import Property
from apps.statistics.services import breakdowns, key_figures


class PublicMunicipalitySerializer(serializers.Serializer):
    """The municipality itself. Contact details only, never internal notes."""

    name = serializers.CharField()
    official_name = serializers.CharField()
    municipality_key = serializers.CharField()
    state = serializers.CharField(source="get_state_display")
    website = serializers.URLField()
    contact_email = serializers.EmailField()


class PublicPropertySerializer(serializers.Serializer):
    """A published object as the outside world may see it.

    Explicitly a plain Serializer over named fields: a ModelSerializer with
    ``exclude`` would silently start publishing any field added later.
    """

    reference = serializers.CharField()
    address = serializers.CharField(source="address_line")
    postal_code = serializers.CharField()
    city = serializers.CharField()
    district = serializers.SerializerMethodField()
    property_type = serializers.CharField(source="get_property_type_display")
    last_known_use = serializers.CharField(source="get_last_known_use_display")
    vacancy_status = serializers.CharField(source="get_vacancy_status_display")
    is_vacant = serializers.BooleanField()
    condition = serializers.CharField(source="get_condition_display")
    heritage_protected = serializers.BooleanField(source="is_heritage_protected")
    in_redevelopment_area = serializers.BooleanField()
    description = serializers.CharField(source="public_description")
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    year_built = serializers.IntegerField()
    recorded_on = serializers.DateField()
    photo = serializers.SerializerMethodField()

    def get_district(self, obj):
        return obj.district.name if obj.district_id else None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_photo(self, obj):
        for document in obj.documents.all():
            if document.kind == DocumentKind.PHOTO and document.is_public:
                return document.file.url
        return None


class PublicAccessMixin:
    """Shared gate for the public area."""

    permission_classes = [AllowAny, HasApiScope]
    required_scope = "read_public"

    def public_organization(self):
        organization = api_organization(self.request)
        if organization is None:
            return None
        municipality = getattr(organization, "municipality", None)
        if municipality is None or not municipality.module_enabled(Module.PUBLIC_API):
            return None
        return organization


@extend_schema(tags=["public"])
class PublicPropertyViewSet(
    PublicAccessMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Objects a municipality has released for publication."""

    serializer_class = PublicPropertySerializer
    lookup_field = "reference"

    def get_queryset(self):
        organization = self.public_organization()
        if organization is None:
            return Property.objects.none()
        queryset = (
            Property.objects.for_organization(organization)
            .public()
            .select_related("district")
            .prefetch_related("documents")
        )
        vacant_only = self.request.query_params.get("vacant")
        if vacant_only in ("1", "true", "yes"):
            queryset = queryset.vacant()
        district = self.request.query_params.get("district")
        if district:
            queryset = queryset.filter(district__name__iexact=district)
        return queryset


@extend_schema(tags=["public"])
class PublicStatisticsView(PublicAccessMixin, APIView):
    """Aggregated key figures. Counts only, no individual objects."""

    required_scope = "read_statistics"

    def get(self, request):
        organization = self.public_organization()
        if organization is None:
            return Response({"detail": _("No municipality resolved.")}, status=404)
        figures = key_figures(organization)
        # Operational numbers say more about the administration's workload than
        # about vacancy, so the public figures stop at the substantive ones.
        public_keys = (
            "total_records",
            "confirmed_records",
            "confirmed_vacancies",
            "critical_records",
            "heritage_vacancies",
            "published_records",
        )
        return Response(
            {
                "municipality": PublicMunicipalitySerializer(
                    organization.municipality
                ).data,
                "figures": {key: figures[key] for key in public_keys},
                "breakdowns": breakdowns(organization),
            }
        )


@extend_schema(tags=["public"])
class PublicMunicipalityView(PublicAccessMixin, APIView):
    """Who runs this instance."""

    def get(self, request):
        organization = self.public_organization()
        if organization is None:
            return Response({"detail": _("No municipality resolved.")}, status=404)
        return Response(PublicMunicipalitySerializer(organization.municipality).data)
