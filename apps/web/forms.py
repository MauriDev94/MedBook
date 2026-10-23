"""Web UI forms: input format only; business rules stay in the services."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import password_validators_help_text_html
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.users.services import validate_patient_registration

# Tailwind only scans apps/web, so widget classes must be written out here.
INPUT_CLASSES = (
    "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm "
    "shadow-sm focus:border-teal-600 focus:ring-1 focus:ring-teal-600 "
    "focus:outline-none aria-invalid:border-red-500"
)


class StyledFormMixin:
    """Give every widget the shared input classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASSES)


class LoginForm(StyledFormMixin, AuthenticationForm):
    """Email + password. The field keeps Django's name, `username`."""

    error_messages = {
        **AuthenticationForm.error_messages,
        # Same text for an unknown email, a wrong password and an inactive
        # account: the form never reveals whether an email is registered.
        "invalid_login": _("Incorrect email or password."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Email")
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "email", "inputmode": "email"}
        )


class SignupForm(StyledFormMixin, forms.Form):
    """Patient sign-up. Rules come from validate_patient_registration().

    Service errors are keyed by field ("email", "password"), so they land
    on the matching form fields. The view still calls register_patient(),
    which re-checks them inside its transaction.
    """

    first_name = forms.CharField(
        label=_("First name"),
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label=_("Last name"),
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        # Lazy: rendered in the language active at request time
        help_text=password_validators_help_text_html(),
    )
    password_confirm = forms.CharField(
        label=_("Confirm password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("password_confirm"):
            self.add_error("password_confirm", _("The passwords do not match."))
        if cleaned_data.get("email") and password:
            try:
                validate_patient_registration(**self.registration_data())
            except ValidationError as exc:
                self.add_error(None, exc)
        return cleaned_data

    def registration_data(self) -> dict:
        """The cleaned fields register_patient() takes (no confirmation)."""
        fields = ("first_name", "last_name", "email", "password")
        return {field: self.cleaned_data.get(field, "") for field in fields}
