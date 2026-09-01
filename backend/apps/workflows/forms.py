from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.workflows.models import Task, TaskStatus, TaskType
from organizations.models import ASSIGNABLE_ROLES


class TaskForm(forms.ModelForm):
    """Create or edit a task.

    The assignee list is limited to people who hold a role that may actually be
    given work in this municipality, so a task cannot be parked on a citizen.
    """

    class Meta:
        model = Task
        fields = (
            "task_type",
            "title",
            "description",
            "property",
            "assignee",
            "priority",
            "due_on",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization is not None:
            from apps.properties.models import Property

            self.fields["property"].queryset = Property.objects.filter(
                organization=organization
            )
            self.fields["assignee"].queryset = (
                get_user_model()
                .objects.filter(
                    memberships__organization=organization,
                    memberships__role__in=ASSIGNABLE_ROLES,
                )
                .distinct()
            )
        self.fields["assignee"].required = False
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save task")))


class TaskFilterForm(forms.Form):
    status = forms.ChoiceField(label=_("status"), required=False, choices=())
    task_type = forms.ChoiceField(label=_("type"), required=False, choices=())
    mine = forms.BooleanField(label=_("only mine"), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        blank = [("", _("all"))]
        self.fields["status"].choices = blank + list(TaskStatus.choices)
        self.fields["task_type"].choices = blank + list(TaskType.choices)


class TaskCompletionForm(forms.Form):
    completion_note = forms.CharField(
        label=_("note"), widget=forms.Textarea(attrs={"rows": 2}), required=False
    )
