from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.municipalities.models import District, Module, Municipality


class MunicipalityForm(forms.ModelForm):
    """Everything a municipality can change about its own instance.

    Geometry is deliberately absent: boundaries are imported from official
    geodata, not typed into a form.
    """

    class Meta:
        model = Municipality
        fields = (
            "name",
            "official_name",
            "municipality_key",
            "state",
            "district_name",
            "contact_email",
            "contact_phone",
            "postal_address",
            "website",
            "domain",
            "logo",
            "coat_of_arms",
            "primary_colour",
            "accent_colour",
            "font_family",
            "default_zoom",
            "public_intro",
            "imprint",
            "privacy_notice",
            "terms",
        )
        widgets = {
            "primary_colour": forms.TextInput(attrs={"type": "color"}),
            "accent_colour": forms.TextInput(attrs={"type": "color"}),
            "postal_address": forms.Textarea(attrs={"rows": 3}),
            "public_intro": forms.Textarea(attrs={"rows": 4}),
            "imprint": forms.Textarea(attrs={"rows": 6}),
            "privacy_notice": forms.Textarea(attrs={"rows": 6}),
            "terms": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))


class ModuleActivationForm(forms.Form):
    """One checkbox per optional module, prefilled with the current state."""

    def __init__(self, *args, municipality=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipality = municipality
        for module in Module:
            self.fields[module.value] = forms.BooleanField(
                label=module.label,
                required=False,
                initial=municipality.module_enabled(module) if municipality else False,
            )
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save modules")))

    def save(self):
        for module in Module:
            self.municipality.set_module(module, self.cleaned_data.get(module.value, False))
        return self.municipality


class DistrictForm(forms.ModelForm):
    class Meta:
        model = District
        fields = ("name", "kind", "code", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))
