from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.workflows.forms import TaskCompletionForm, TaskFilterForm, TaskForm
from apps.workflows.models import Task
from organizations.mixins import (
    CurrentOrganizationRequiredMixin,
    OrgScopedQuerysetMixin,
    StaffRoleRequiredMixin,
    VerificationRoleRequiredMixin,
)


class TaskListView(
    CurrentOrganizationRequiredMixin,
    VerificationRoleRequiredMixin,
    OrgScopedQuerysetMixin,
    ListView,
):
    """The work list.

    Verified contributors see it too, because tasks can be assigned to them;
    what they see is filtered to their own assignments.
    """

    model = Task
    template_name = "workflows/task_list.html"
    context_object_name = "tasks"
    paginate_by = 25

    def get_filter_form(self):
        return TaskFilterForm(self.request.GET or None)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("property", "assignee")
        if not self.request.organization.is_staff_member(self.request.user):
            # A contributor is shown their own work, not the whole backlog.
            queryset = queryset.assigned_to(self.request.user)
        form = self.get_filter_form()
        if not form.is_valid():
            return queryset
        data = form.cleaned_data
        if data.get("status"):
            queryset = queryset.filter(status=data["status"])
        if data.get("task_type"):
            queryset = queryset.filter(task_type=data["task_type"])
        if data.get("mine"):
            queryset = queryset.assigned_to(self.request.user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scoped = Task.objects.for_organization(self.request.organization)
        context["filter_form"] = self.get_filter_form()
        context["open_count"] = scoped.open().count()
        context["overdue_count"] = scoped.overdue().count()
        context["can_manage"] = self.request.organization.is_staff_member(self.request.user)
        context["completion_form"] = TaskCompletionForm()
        return context


class TaskCreateView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, OrgScopedQuerysetMixin, CreateView
):
    model = Task
    form_class = TaskForm
    template_name = "workflows/task_form.html"
    success_url = reverse_lazy("workflows:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, _("Task created."))
        return super().form_valid(form)


class TaskUpdateView(
    CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, OrgScopedQuerysetMixin, UpdateView
):
    model = Task
    form_class = TaskForm
    template_name = "workflows/task_form.html"
    success_url = reverse_lazy("workflows:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs


class TaskCompleteView(CurrentOrganizationRequiredMixin, VerificationRoleRequiredMixin, View):
    """Mark a task done.

    A contributor may only close a task that was given to them.
    """

    def post(self, request, pk):
        task = get_object_or_404(
            Task.objects.filter(organization=request.organization), pk=pk
        )
        if not request.organization.is_staff_member(request.user) and task.assignee_id != (
            request.user.pk
        ):
            messages.error(request, _("This task is not assigned to you."))
            return redirect("workflows:list")
        form = TaskCompletionForm(request.POST)
        note = form.cleaned_data.get("completion_note", "") if form.is_valid() else ""
        task.complete(actor=request.user, note=note)
        messages.success(request, _("Task completed."))
        return redirect("workflows:list")


class TaskReopenView(CurrentOrganizationRequiredMixin, StaffRoleRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(
            Task.objects.filter(organization=request.organization), pk=pk
        )
        task.reopen()
        messages.success(request, _("Task reopened."))
        return redirect("workflows:list")
