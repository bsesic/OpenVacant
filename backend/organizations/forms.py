from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from organizations.models import Invitation, Organization, Role


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Create organization")))


class InvitationForm(forms.ModelForm):
    # Owners cannot be invited; ownership is granted explicitly.
    role = forms.ChoiceField(
        choices=[(Role.ADMIN.value, Role.ADMIN.label), (Role.MEMBER.value, Role.MEMBER.label)],
        initial=Role.MEMBER.value,
    )

    class Meta:
        model = Invitation
        fields = ("email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Send invitation")))
