from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.integrations.models import ApiClient, Scope


class ApiClientForm(forms.ModelForm):
    """Issue or edit an external client.

    Scopes are checkboxes rather than a free field: granting access should be a
    series of deliberate decisions about individual capabilities.
    """

    scope_choices = forms.MultipleChoiceField(
        label=_("scopes"),
        choices=Scope.choices,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = ApiClient
        fields = (
            "name",
            "description",
            "contact_email",
            "expires_at",
            "throttle_rate",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["scope_choices"].initial = self.instance.scopes
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Save")))

    def clean_throttle_rate(self):
        rate = self.cleaned_data["throttle_rate"]
        # Parsed the same way DRF will parse it, so a typo fails here rather
        # than at the first request from the client.
        try:
            count, _sep, period = rate.partition("/")
            int(count)
            if not period or period[0] not in "smhd":
                raise ValueError
        except (ValueError, AttributeError):
            raise forms.ValidationError(
                _("Use a rate such as 1000/hour, 60/min or 10/second.")
            ) from None
        return rate
