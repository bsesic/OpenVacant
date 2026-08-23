"""Administrative API.

The professional data, for the municipality's own staff and for external systems
the municipality has explicitly granted internal access. Everything here is
gated twice: by the caller's role or scope, and by the tenant.
"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.resolution import api_organization
from apps.integrations.authentication import HasApiScope
from apps.inspections.models import Inspection
from apps.properties.models import Property
from apps.reports.models import Report
from apps.statistics.services import breakdowns, key_figures, monthly_series
from apps.workflows.models import Task


class IsInternalCaller(BasePermission):
    """Allow municipal staff, or a client holding the internal-read scope.

    A signed-in person needs an internal role in the tenant; a citizen with an
    account must not reach this area just because they are authenticated.
    """

    message = _("This area is reserved for the administration.")

    def has_permission(self, request, view):
        client = getattr(request, "api_client", None)
        if client is not None:
            return True  # The scope check is HasApiScope's job.
        if not request.user.is_authenticated:
            return False
        organization = api_organization(request)
        if organization is None:
            return False
        return organization.has_internal_access(request.user)


class InternalAreaMixin:
    permission_classes = [IsAuthenticated, IsInternalCaller, HasApiScope]
    required_scope = "read_internal"

    def internal_organization(self):
        return api_organization(self.request)


class AdminPropertySerializer(serializers.ModelSerializer):
    """The full record. Only ever served inside the administrative area."""

    district_name = serializers.CharField(source="district.name", read_only=True, default=None)
    address = serializers.CharField(source="address_line", read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    damages = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = (
            "id",
            "reference",
            "address",
            "street",
            "house_number",
            "postal_code",
            "city",
            "address_note",
            "latitude",
            "longitude",
            "district",
            "district_name",
            "property_type",
            "last_known_use",
            "status",
            "vacancy_status",
            "condition",
            "condition_source",
            "priority",
            "recorded_on",
            "last_checked_on",
            "public_description",
            "internal_description",
            "sources",
            "is_public",
            "plot_area_sqm",
            "usable_area_sqm",
            "living_area_sqm",
            "year_built",
            "units_total",
            "units_vacant",
            "is_heritage_protected",
            "in_redevelopment_area",
            "in_funding_area",
            "in_development_area",
            "damages",
            "allowed_transitions",
            "created_at",
            "updated_at",
        )
        # The workflow status changes through its own action so the audit trail
        # stays complete; the same rule applies over the API.
        read_only_fields = (
            "id",
            "reference",
            "status",
            "vacancy_status",
            "last_checked_on",
            "created_at",
            "updated_at",
        )

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_damages(self, obj):
        return [
            {"type": damage.damage_type, "severity": damage.severity, "source": damage.source}
            for damage in obj.damages.all()
        ]

    def get_allowed_transitions(self, obj):
        return obj.allowed_transitions()


class AdminReportSerializer(serializers.ModelSerializer):
    address = serializers.CharField(source="address_line", read_only=True)
    property_reference = serializers.CharField(
        source="property.reference", read_only=True, default=None
    )

    class Meta:
        model = Report
        fields = (
            "id",
            "reference",
            "category",
            "status",
            "description",
            "address",
            "damage_types",
            "contact_name",
            "contact_email",
            "contact_phone",
            "wants_feedback",
            "property",
            "property_reference",
            "created_at",
        )
        read_only_fields = fields


class AdminInspectionSerializer(serializers.ModelSerializer):
    property_reference = serializers.CharField(source="property.reference", read_only=True)

    class Meta:
        model = Inspection
        fields = (
            "id",
            "property",
            "property_reference",
            "kind",
            "result",
            "inspected_on",
            "inspector_role",
            "observed_vacancy_status",
            "observed_condition",
            "observed_damage",
            "findings",
            "applied_at",
        )
        read_only_fields = fields


class AdminTaskSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "label",
            "task_type",
            "title",
            "description",
            "property",
            "report",
            "assignee",
            "status",
            "priority",
            "due_on",
            "completed_at",
        )
        read_only_fields = ("id", "label", "completed_at")


@extend_schema(tags=["administration"])
class AdminPropertyViewSet(InternalAreaMixin, viewsets.ModelViewSet):
    """The property records of the caller's municipality."""

    serializer_class = AdminPropertySerializer

    def get_queryset(self):
        organization = self.internal_organization()
        if organization is None:
            return Property.objects.none()
        return (
            Property.objects.for_organization(organization)
            .select_related("district")
            .prefetch_related("damages")
        )

    def perform_create(self, serializer):
        serializer.save(
            organization=self.internal_organization(),
            created_by=self.request.user if self.request.user.pk else None,
        )


@extend_schema(tags=["administration"])
class AdminReportViewSet(
    InternalAreaMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = AdminReportSerializer

    def get_queryset(self):
        organization = self.internal_organization()
        if organization is None:
            return Report.objects.none()
        return Report.objects.for_organization(organization).select_related("property")


@extend_schema(tags=["administration"])
class AdminInspectionViewSet(
    InternalAreaMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = AdminInspectionSerializer

    def get_queryset(self):
        organization = self.internal_organization()
        if organization is None:
            return Inspection.objects.none()
        return Inspection.objects.for_organization(organization).select_related("property")


@extend_schema(tags=["administration"])
class AdminTaskViewSet(InternalAreaMixin, viewsets.ModelViewSet):
    serializer_class = AdminTaskSerializer

    def get_queryset(self):
        organization = self.internal_organization()
        if organization is None:
            return Task.objects.none()
        return Task.objects.for_organization(organization).select_related("property")

    def perform_create(self, serializer):
        serializer.save(organization=self.internal_organization())


@extend_schema(tags=["administration"])
class AdminStatisticsView(InternalAreaMixin, APIView):
    """The full key figures, including the operational ones."""

    required_scope = "read_statistics"

    def get(self, request):
        organization = self.internal_organization()
        if organization is None:
            return Response({"detail": _("No municipality resolved.")}, status=404)
        return Response(
            {
                "figures": key_figures(organization),
                "breakdowns": breakdowns(organization),
                "series": monthly_series(organization),
            }
        )
