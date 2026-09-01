from django import forms
from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.properties.choices import DamageType
from apps.reports.models import Report, ReportCategory, ReportStatus


class MultipleFileInput(forms.ClearableFileInput):
    """File input that accepts several files at once.

    Django refuses ``multiple`` on the plain widget, so opting in explicitly is
    the documented way to allow it.
    """

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field whose cleaned value is always a list of uploads."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data if item]
        return [clean_one(data, initial)] if data else []


class ReportForm(forms.ModelForm):
    """The citizen report form.

    Deliberately short. Everything except the location and the consent is
    optional, because a report that is abandoned halfway is worth nothing, and
    the administration would rather have a marker and a photo than a complete
    form nobody fills in.
    """

    # The map writes the marker into these; they are hidden rather than a
    # geometry widget so the form works without a JavaScript map as well.
    latitude = forms.FloatField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_latitude"})
    )
    longitude = forms.FloatField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_longitude"})
    )

    damage = forms.MultipleChoiceField(
        label=_("Visible damage"),
        choices=DamageType.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Only what you can see from the street."),
    )

    photos = MultipleFileField(
        label=_("Photos"),
        required=False,
        help_text=_("Please do not photograph people, and avoid private property."),
    )

    accepted_privacy_policy = forms.BooleanField(
        label=_("I have read the privacy notice."), required=True
    )
    accepted_terms = forms.BooleanField(label=_("I accept the terms of use."), required=True)

    # Bots fill in every field they find. A human never sees this one, so a
    # value in it is a reliable spam signal that costs the reporter nothing.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
        label=_("Website"),
    )

    class Meta:
        model = Report
        fields = (
            "category",
            "description",
            "street",
            "house_number",
            "postal_code",
            "city",
            "contact_name",
            "contact_email",
            "contact_phone",
            "wants_feedback",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "category": forms.RadioSelect,
        }

    def __init__(self, *args, municipality=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipality = municipality
        self.user = user
        self.field_order = None
        if municipality is not None and municipality.name:
            self.fields["city"].initial = municipality.name
        if user is not None and user.is_authenticated:
            # A signed-in reporter is already identified; asking again is noise.
            for name in ("contact_name", "contact_email", "contact_phone"):
                self.fields.pop(name)
            self.fields["wants_feedback"].help_text = _(
                "We will use the email address of your account."
            )

    def clean_photos(self):
        """Enforce the photo count and size limits across all uploaded files."""
        files = self.cleaned_data.get("photos") or []
        max_count = settings.REPORT_MAX_PHOTOS
        if len(files) > max_count:
            raise forms.ValidationError(
                _("Please upload at most %(count)d photos.") % {"count": max_count}
            )
        max_bytes = settings.REPORT_MAX_PHOTO_SIZE_MB * 1024 * 1024
        for uploaded in files:
            if uploaded.size > max_bytes:
                raise forms.ValidationError(
                    _("“%(name)s” is larger than %(limit)d MB.")
                    % {"name": uploaded.name, "limit": settings.REPORT_MAX_PHOTO_SIZE_MB}
                )
        return files

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError(_("Your report could not be submitted."))
        return value

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if latitude is not None and longitude is not None:
            cleaned["location"] = Point(longitude, latitude, srid=4326)
        else:
            cleaned["location"] = None

        has_address = bool(cleaned.get("street") or cleaned.get("city"))
        if cleaned["location"] is None and not has_address:
            raise forms.ValidationError(
                _("Please mark the building on the map or enter its address.")
            )

        wants_feedback = cleaned.get("wants_feedback")
        signed_in = self.user is not None and self.user.is_authenticated
        if wants_feedback and not signed_in and not cleaned.get("contact_email"):
            self.add_error(
                "wants_feedback",
                _("Please leave an email address if you would like to hear back."),
            )
        return cleaned

    def save(self, commit=True, organization=None, ip_address=None):
        report = super().save(commit=False)
        report.organization = organization
        report.location = self.cleaned_data.get("location")
        report.damage_types = self.cleaned_data.get("damage") or []
        report.consent_given_at = timezone.now()
        report.submitted_from_ip = ip_address
        if self.user is not None and self.user.is_authenticated:
            report.submitted_by = self.user
        municipality = self.municipality
        if municipality is not None and report.location is not None:
            report.district = municipality.district_for_point(report.location)
        if commit:
            report.save()
            for uploaded in self.cleaned_data.get("photos") or []:
                report.photos.create(image=uploaded)
        return report


class ReportModerationForm(forms.Form):
    """A moderation decision on one report."""

    status = forms.ChoiceField(
        label=_("decision"),
        choices=[
            (ReportStatus.IN_MODERATION.value, ReportStatus.IN_MODERATION.label),
            (ReportStatus.DUPLICATE.value, ReportStatus.DUPLICATE.label),
            (ReportStatus.REJECTED.value, ReportStatus.REJECTED.label),
            (ReportStatus.SPAM.value, ReportStatus.SPAM.label),
        ],
    )
    moderation_note = forms.CharField(
        label=_("note"), widget=forms.Textarea(attrs={"rows": 2}), required=False
    )


class ReportFilterForm(forms.Form):
    q = forms.CharField(label=_("search"), required=False)
    status = forms.ChoiceField(label=_("status"), required=False, choices=())
    category = forms.ChoiceField(label=_("category"), required=False, choices=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        blank = [("", _("all"))]
        self.fields["status"].choices = blank + list(ReportStatus.choices)
        self.fields["category"].choices = blank + list(ReportCategory.choices)
