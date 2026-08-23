"""Citizen API.

Everything a person can do about their own involvement: file a report, and see
what happened to the ones they filed. Nothing here reads anybody else's data.
"""

from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from api.resolution import api_organization
from apps.municipalities.models import Module
from apps.properties.choices import DamageType
from apps.reports.models import Report, ReportCategory


class ReportCreateSerializer(serializers.Serializer):
    """A new report.

    Mirrors the web form, including that either a coordinate or an address is
    enough, and that consent is mandatory and recorded.
    """

    category = serializers.ChoiceField(
        choices=ReportCategory.choices, default=ReportCategory.SUSPECTED_VACANCY
    )
    description = serializers.CharField(required=False, allow_blank=True)
    street = serializers.CharField(required=False, allow_blank=True, max_length=255)
    house_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=16)
    city = serializers.CharField(required=False, allow_blank=True, max_length=120)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    damage = serializers.ListField(
        child=serializers.ChoiceField(choices=DamageType.choices), required=False
    )
    contact_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=50)
    wants_feedback = serializers.BooleanField(default=False)
    accepted_privacy_policy = serializers.BooleanField()
    accepted_terms = serializers.BooleanField()

    def validate_accepted_privacy_policy(self, value):
        if not value:
            raise serializers.ValidationError(_("The privacy notice has to be accepted."))
        return value

    def validate_accepted_terms(self, value):
        if not value:
            raise serializers.ValidationError(_("The terms of use have to be accepted."))
        return value

    def validate(self, attrs):
        has_point = attrs.get("latitude") is not None and attrs.get("longitude") is not None
        has_address = bool(attrs.get("street") or attrs.get("city"))
        if not has_point and not has_address:
            raise serializers.ValidationError(
                _("Either a coordinate or an address is required.")
            )
        if attrs.get("wants_feedback") and not (
            attrs.get("contact_email") or self.context.get("user_email")
        ):
            raise serializers.ValidationError(
                {"wants_feedback": _("Feedback needs an email address.")}
            )
        return attrs

    def create(self, validated_data):
        organization = self.context["organization"]
        latitude = validated_data.pop("latitude", None)
        longitude = validated_data.pop("longitude", None)
        damage = validated_data.pop("damage", [])
        user = self.context.get("user")

        return Report.objects.create(
            organization=organization,
            location=(
                Point(longitude, latitude, srid=4326)
                if latitude is not None and longitude is not None
                else None
            ),
            damage_types=damage,
            consent_given_at=timezone.now(),
            submitted_by=user if user is not None and user.is_authenticated else None,
            **validated_data,
        )


class MyReportSerializer(serializers.Serializer):
    """A report as its own submitter may see it."""

    reference = serializers.CharField()
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    address = serializers.CharField(source="address_line")
    description = serializers.CharField()
    submitted_at = serializers.DateTimeField(source="created_at")
    # The submitter learns that their report led somewhere, not what the
    # administration wrote about the building.
    became_record = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_became_record(self, obj):
        return obj.property.reference if obj.property_id else None


class ReportSubmissionThrottle(AnonRateThrottle):
    """Same idea as the web form's limit, applied to the API."""

    scope = "report_submission"


@extend_schema(tags=["citizen"])
class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Submit a report, and list your own."""

    serializer_class = MyReportSerializer
    # Creating deliberately does not require an account, mirroring the anonymous
    # web form; listing is about a person's own reports and therefore does.
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action == "create":
            return [ReportSubmissionThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Report.objects.none()
        return Report.objects.filter(submitted_by=self.request.user).select_related("property")

    def get_serializer_class(self):
        if self.action == "create":
            return ReportCreateSerializer
        return MyReportSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = api_organization(self.request)
        context["organization"] = organization
        context["user"] = self.request.user
        context["user_email"] = getattr(self.request.user, "email", "")
        return context

    def create(self, request, *args, **kwargs):
        organization = api_organization(request)
        if organization is None:
            return self._error(_("No municipality could be determined for this report."), 400)

        municipality = getattr(organization, "municipality", None)
        if (
            not request.user.is_authenticated
            and municipality is not None
            and not municipality.module_enabled(Module.ANONYMOUS_REPORTS)
        ):
            return self._error(_("This municipality requires an account for reports."), 403)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(MyReportSerializer(report).data, status=201)

    @staticmethod
    def _error(detail, status):
        return Response({"detail": detail}, status=status)
