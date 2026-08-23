from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.inspections.models import Inspection
from apps.properties.choices import DamageType
from apps.reports.forms import MultipleFileField


class InspectionForm(forms.ModelForm):
    """Record what was established during a verification."""

    observed_damage_types = forms.MultipleChoiceField(
        label=_("observed damage"),
        choices=DamageType.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    photos = MultipleFileField(label=_("photos"), required=False)

    class Meta:
        model = Inspection
        fields = (
            "kind",
            "result",
            "inspected_on",
            "observed_vacancy_status",
            "observed_condition",
            "findings",
        )
        widgets = {
            "inspected_on": forms.DateInput(attrs={"type": "date"}),
            "findings": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Record verification")))

    def save(self, commit=True, organization=None, record=None, inspector=None, role=""):
        inspection = super().save(commit=False)
        inspection.organization = organization
        inspection.property = record
        inspection.inspector = inspector
        inspection.inspector_role = role
        inspection.observed_damage = self.cleaned_data.get("observed_damage_types") or []
        if commit:
            inspection.save()
            for uploaded in self.cleaned_data.get("photos") or []:
                inspection.photos.create(image=uploaded)
        return inspection
