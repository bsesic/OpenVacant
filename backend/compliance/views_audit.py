"""Reading the access log from inside the administration."""

from django.views.generic import ListView

from compliance.models import AccessLog
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    OrganizationManagerRequiredMixin,
)


class AccessLogView(
    CurrentOrganizationRequiredMixin, OrganizationManagerRequiredMixin, ListView
):
    """Who looked at personal or internal data in this municipality.

    Restricted to managers rather than all staff: the log is also a record of
    what colleagues did, and it should not be casually browsable.
    """

    model = AccessLog
    template_name = "compliance/access_log.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        queryset = AccessLog.objects.filter(
            organization=self.request.organization
        ).select_related("actor")
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_context_data(self, **kwargs):
        from compliance.models import AccessCategory

        context = super().get_context_data(**kwargs)
        context["categories"] = AccessCategory.choices
        context["selected_category"] = self.request.GET.get("category", "")
        return context
