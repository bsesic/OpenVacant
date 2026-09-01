from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.documents.models import NEVER_PUBLIC_KINDS, PropertyDocument, Visibility


class PropertyDocumentForm(forms.ModelForm):
    class Meta:
        model = PropertyDocument
        fields = ("kind", "title", "description", "file", "visibility", "recorded_on")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "recorded_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Upload")))

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind in NEVER_PUBLIC_KINDS and cleaned.get("visibility") == Visibility.PUBLIC:
            self.add_error(
                "visibility",
                _("Documents of this kind cannot be published."),
            )
        return cleaned
