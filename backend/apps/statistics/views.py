import csv
import json

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from apps.properties.models import Property
from apps.statistics.models import KeyFigureSnapshot
from apps.statistics.services import breakdowns, dashboard_context, key_figures
from compliance.audit import log_access
from compliance.models import AccessCategory
from organizations.mixins import CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin


class DashboardView(CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, TemplateView):
    """The administration's working surface."""

    template_name = "statistics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.organization
        context.update(dashboard_context(organization))
        context["series_json"] = json.dumps(context["series"])
        context["snapshots"] = KeyFigureSnapshot.objects.for_organization(organization)[:12]
        return context


class DashboardMapDataView(CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, View):
    """GeoJSON of the municipality's own records, for the dashboard map.

    Unlike the public endpoint this includes unpublished records — it is behind
    the internal-area check — but still no internal free text, because the map
    popup is not the place to read case notes.
    """

    def get(self, request):
        records = (
            Property.objects.for_organization(request.organization)
            .exclude(location__isnull=True)
            .select_related("district")
        )
        for field in ("status", "vacancy_status", "condition", "district"):
            value = request.GET.get(field)
            if not value:
                continue
            if field == "district":
                records = records.filter(district_id=value)
            else:
                records = records.filter(**{field: value})

        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [record.location.x, record.location.y],
                },
                "properties": {
                    "reference": record.reference,
                    "address": record.address_line,
                    "district": record.district.name if record.district else None,
                    "status": record.get_status_display(),
                    "vacancy_status": record.get_vacancy_status_display(),
                    "condition": record.get_condition_display(),
                    "priority": record.get_priority_display(),
                    "is_vacant": record.is_vacant,
                    "is_critical": record.is_critical,
                    "is_public": record.is_public,
                    "url": record.get_absolute_url(),
                },
            }
            for record in records
        ]
        return JsonResponse({"type": "FeatureCollection", "features": features})


class KeyFigureExportView(CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, View):
    """Key figures as CSV, for reports and funding applications."""

    def get(self, request):
        organization = request.organization
        figures = key_figures(organization)
        parts = breakdowns(organization)
        log_access(
            request.user,
            AccessCategory.BULK_EXPORT,
            organization=organization,
            object_reference="key-figures",
            purpose="Key figure export",
        )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="key-figures.csv"'
        writer = csv.writer(response)
        writer.writerow(["group", "key", "value"])
        for key, value in figures.items():
            writer.writerow(["summary", key, value])
        for group, entries in parts.items():
            for entry in entries:
                writer.writerow([group, entry["label"], entry["count"]])
        return response
