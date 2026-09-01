from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.parcels.models import Parcel
from apps.properties.choices import RecordStatus, VacancyStatus
from apps.properties.models import Property, PropertyDamage


class PropertyForm(forms.ModelForm):
    """The professional record.

    The workflow status and the occupancy status are deliberately absent: both
    have to go through their own action so the audit trail and the vacancy
    timeline cannot be bypassed by an ordinary edit.
    """

    class Meta:
        model = Property
        fields = (
            "district",
            "street",
            "house_number",
            "postal_code",
            "city",
            "address_note",
            "location",
            "property_type",
            "last_known_use",
            "condition",
            "condition_source",
            "priority",
            "recorded_on",
            "public_description",
            "internal_description",
            "sources",
            "is_public",
            "parcels",
            "plot_area_sqm",
            "usable_area_sqm",
            "living_area_sqm",
            "year_built",
            "units_total",
            "units_vacant",
        )
        widgets = {
            "public_description": forms.Textarea(attrs={"rows": 3}),
            "internal_description": forms.Textarea(attrs={"rows": 3}),
            "sources": forms.Textarea(attrs={"rows": 2}),
            "recorded_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization is not None:
            municipality = getattr(organization, "municipality", None)
            districts = (
                municipality.districts.all()
                if municipality is not None
                else self.fields["district"].queryset.none()
            )
            self.fields["district"].queryset = districts
            self.fields["parcels"].queryset = Parcel.objects.filter(organization=organization)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))


class StatusTransitionForm(forms.Form):
    """Move a record to the next status, with a reason for the audit trail."""

    status = forms.ChoiceField(label=_("new status"), choices=())
    reason = forms.CharField(label=_("reason"), max_length=255, required=False)
    note = forms.CharField(label=_("note"), widget=forms.Textarea(attrs={"rows": 2}),
                           required=False)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        allowed = instance.allowed_transitions() if instance is not None else []
        self.fields["status"].choices = [
            (status, RecordStatus(status).label) for status in allowed
        ]
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Change status")))


class VacancyStatusForm(forms.Form):
    """Record a change in occupancy, which also extends the vacancy history."""

    vacancy_status = forms.ChoiceField(label=_("occupancy"), choices=VacancyStatus.choices)
    source = forms.CharField(label=_("source"), max_length=255, required=False)
    note = forms.CharField(label=_("note"), widget=forms.Textarea(attrs={"rows": 2}),
                           required=False)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance is not None:
            self.fields["vacancy_status"].initial = instance.vacancy_status
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Record occupancy")))


class DamageForm(forms.ModelForm):
    class Meta:
        model = PropertyDamage
        fields = ("damage_type", "severity", "source", "note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Add damage")))


class PropertyFilterForm(forms.Form):
    """Filters for the record list, matching the dashboard's filter set."""

    q = forms.CharField(label=_("search"), required=False)
    status = forms.ChoiceField(label=_("status"), required=False, choices=())
    vacancy_status = forms.ChoiceField(label=_("occupancy"), required=False, choices=())
    condition = forms.ChoiceField(label=_("condition"), required=False, choices=())
    district = forms.ChoiceField(label=_("district"), required=False, choices=())

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.properties.choices import ConditionGrade

        blank = [("", _("all"))]
        self.fields["status"].choices = blank + list(RecordStatus.choices)
        self.fields["vacancy_status"].choices = blank + list(VacancyStatus.choices)
        self.fields["condition"].choices = blank + list(ConditionGrade.choices)
        districts = []
        municipality = getattr(organization, "municipality", None) if organization else None
        if municipality is not None:
            districts = [(str(d.pk), d.name) for d in municipality.districts.all()]
        self.fields["district"].choices = blank + districts
