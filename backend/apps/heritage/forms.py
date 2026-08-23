from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.heritage.models import HeritageCheck, MonumentRecord


class HeritageCheckForm(forms.ModelForm):
    class Meta:
        model = HeritageCheck
        fields = ("result", "checked_on", "monument", "authority_reference", "note")
        widgets = {
            "checked_on": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["monument"].queryset = MonumentRecord.objects.filter(
                organization=organization
            )
        self.fields["monument"].required = False
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Record check")))


class MonumentForm(forms.ModelForm):
    class Meta:
        model = MonumentRecord
        fields = (
            "designation",
            "monument_id",
            "scope",
            "authority",
            "listed_on",
            "property",
            "description",
            "source",
        )
        widgets = {
            "listed_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            from apps.properties.models import Property

            self.fields["property"].queryset = Property.objects.filter(
                organization=organization
            )
        self.fields["property"].required = False
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save monument")))
