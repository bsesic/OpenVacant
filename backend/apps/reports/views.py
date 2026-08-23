from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from django_ratelimit.decorators import ratelimit

from apps.municipalities.models import Module
from apps.properties.choices import VACANCY_STATUSES
from apps.properties.models import Property
from apps.reports.forms import ReportFilterForm, ReportForm, ReportModerationForm
from apps.reports.models import Report
from apps.reports.services import (
    attach_report_to_property,
    create_property_from_report,
    start_verification,
)
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    InternalAreaRequiredMixin,
    OrgScopedQuerysetMixin,
    StaffRoleRequiredMixin,
)


def client_ip(request):
    """The reporter's address, honouring one layer of trusted proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _module_enabled(municipality, module):
    return municipality is not None and municipality.module_enabled(module)


# --- Citizen surface -------------------------------------------------------


@method_decorator(
    ratelimit(key="ip", rate=settings.REPORT_RATE_LIMIT, method="POST", block=True),
    name="post",
)
class ReportCreateView(CreateView):
    """The citizen report form.

    Open to anonymous visitors when the municipality allows it, because a
    mandatory account is the single biggest obstacle to a low-barrier report.
    Rate limiting and the honeypot field carry the abuse protection instead.
    """

    model = Report
    form_class = ReportForm
    template_name = "reports/report_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.municipality = getattr(request, "municipality", None) or None
        if self.municipality is None:
            # With no municipality resolved there is nobody to route the report
            # to, so offering the form would be dishonest.
            return super().dispatch(request, *args, **kwargs)
        anonymous_allowed = self.municipality.module_enabled(
            Module.ANONYMOUS_REPORTS
        ) and settings.ANONYMOUS_REPORTS_ENABLED
        if not request.user.is_authenticated and not anonymous_allowed:
            messages.info(request, _("Please sign in to submit a report."))
            return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["municipality"] = self.municipality
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["municipality_missing"] = self.municipality is None
        return context

    def form_valid(self, form):
        if self.municipality is None:
            messages.error(
                self.request, _("This installation is not assigned to a municipality yet.")
            )
            return self.form_invalid(form)
        self.object = form.save(
            organization=self.municipality.organization,
            ip_address=client_ip(self.request),
        )
        return redirect(reverse("reports:submitted", kwargs={"reference": self.object.reference}))


class ReportSubmittedView(TemplateView):
    """Confirmation page, showing the reference the reporter can quote."""

    template_name = "reports/report_submitted.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reference"] = self.kwargs["reference"]
        return context


class MyReportsView(ListView):
    """A signed-in reporter's own submissions and what became of them."""

    template_name = "reports/my_reports.html"
    context_object_name = "reports"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Report.objects.filter(submitted_by=self.request.user).select_related("property")


class PublicMapView(TemplateView):
    """The public map of released records."""

    template_name = "reports/public_map.html"

    def dispatch(self, request, *args, **kwargs):
        municipality = getattr(request, "municipality", None) or None
        if municipality is not None and not municipality.module_enabled(Module.PUBLIC_MAP):
            raise PermissionDenied
        self.municipality = municipality
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reporting_enabled"] = _module_enabled(
            self.municipality, Module.ANONYMOUS_REPORTS
        )
        return context


class PublicMapDataView(View):
    """GeoJSON of the released records, for the public map.

    Only published records, and only public fields. This endpoint is the reason
    the record keeps its public and internal descriptions apart.
    """

    def get(self, request):
        municipality = getattr(request, "municipality", None) or None
        if municipality is None or not municipality.module_enabled(Module.PUBLIC_MAP):
            raise PermissionDenied
        records = (
            Property.objects.filter(organization=municipality.organization)
            .public()
            .exclude(location__isnull=True)
            .select_related("district")
        )
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
                    "property_type": record.get_property_type_display(),
                    "condition": record.get_condition_display(),
                    "vacancy_status": record.get_vacancy_status_display(),
                    "is_vacant": record.vacancy_status in VACANCY_STATUSES,
                    "description": record.public_description,
                },
            }
            for record in records
        ]
        return JsonResponse(
            {"type": "FeatureCollection", "features": features}, encoder=DjangoJSONEncoder
        )


# --- Administration surface ------------------------------------------------


class ReportListView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, ListView
):
    """The moderation queue."""

    model = Report
    template_name = "reports/report_list.html"
    context_object_name = "reports"
    paginate_by = 25

    def get_filter_form(self):
        return ReportFilterForm(self.request.GET or None)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("property", "district")
        form = self.get_filter_form()
        if not form.is_valid():
            return queryset
        data = form.cleaned_data
        if data.get("status"):
            queryset = queryset.filter(status=data["status"])
        if data.get("category"):
            queryset = queryset.filter(category=data["category"])
        if data.get("q"):
            query = data["q"]
            queryset = queryset.filter(description__icontains=query) | queryset.filter(
                street__icontains=query
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        context["open_count"] = (
            Report.objects.for_organization(self.request.organization).open().count()
        )
        context["can_moderate"] = self.request.organization.is_staff_member(self.request.user)
        return context


class ReportDetailView(
    CurrentOrganizationRequiredMixin, InternalAreaRequiredMixin, OrgScopedQuerysetMixin, DetailView
):
    model = Report
    template_name = "reports/report_detail.html"
    context_object_name = "report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        context["photos"] = report.photos.all()
        context["moderation_form"] = ReportModerationForm()
        context["can_moderate"] = self.request.organization.is_staff_member(self.request.user)
        # Candidates for attaching the report to a record the register knows.
        context["candidates"] = (
            Property.objects.for_organization(self.request.organization)
            .exclude(pk=report.property_id)
            .order_by("-created_at")[:20]
        )
        return context


class _ReportActionView(CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, View):
    def get_report(self, pk):
        return get_object_or_404(
            Report.objects.filter(organization=self.request.organization), pk=pk
        )


class ReportModerateView(_ReportActionView):
    def post(self, request, pk):
        report = self.get_report(pk)
        form = ReportModerationForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Please choose a decision."))
            return redirect(report.get_absolute_url())
        report.moderate(
            form.cleaned_data["status"],
            actor=request.user,
            note=form.cleaned_data.get("moderation_note", ""),
        )
        messages.success(request, _("Report updated."))
        return redirect(report.get_absolute_url())


class ReportAcceptView(_ReportActionView):
    """Accept a report by creating a record for it, and start the check."""

    def post(self, request, pk):
        report = self.get_report(pk)
        if report.property_id:
            messages.info(request, _("This report is already attached to a record."))
            return redirect(report.get_absolute_url())
        record = create_property_from_report(report, actor=request.user)
        start_verification(record, actor=request.user, reason=_("Created from a citizen report"))
        messages.success(
            request,
            _("Record %(reference)s created and put into the preliminary check.")
            % {"reference": record.reference},
        )
        return redirect(record.get_absolute_url())


class ReportAttachView(_ReportActionView):
    """Attach a report to a record the register already holds."""

    def post(self, request, pk):
        report = self.get_report(pk)
        record = get_object_or_404(
            Property.objects.filter(organization=request.organization),
            pk=request.POST.get("property"),
        )
        attach_report_to_property(report, record, actor=request.user)
        messages.success(request, _("Report attached to the record."))
        return redirect(record.get_absolute_url())


class ReportPhotoPublicationView(_ReportActionView):
    """Release a single report photo, or withdraw it again."""

    def post(self, request, pk, photo_pk):
        report = self.get_report(pk)
        photo = get_object_or_404(report.photos, pk=photo_pk)
        photo.is_public = not photo.is_public
        photo.save(update_fields=["is_public"])
        if photo.is_public:
            messages.success(request, _("Photo released."))
        else:
            messages.success(request, _("Photo withdrawn."))
        return redirect(report.get_absolute_url())
