"""Business logic for the users domain.

Pure Python — no HTTP, no serializers. The registration flow is shared by
the API (PatientRegistrationSerializer) and the web sign-up form
(apps.web.forms.SignupForm, ADR 0002), so every rule lives here and nowhere
else.

Errors are raised as django.core.exceptions.ValidationError keyed by field
name ({"email": [...], "password": [...]}), which DRF and Django forms both
map to per-field errors.
"""

import datetime

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from apps.core.roles import is_patient
from apps.patients.models import Patient
from apps.users.models import Role, User

# Lazy: the web form shows it in the visitor's language; the API resolves
# it while English is active (apps.core.middleware.EnglishApiMiddleware).
DUPLICATE_EMAIL_MESSAGE = _("A user with this email already exists.")


def validate_patient_registration(
    *, email: str, password: str, first_name: str = "", last_name: str = ""
) -> None:
    """Check the registration rules, collecting every field error at once.

    Raises:
        ValidationError: with an "email" key if the email is already taken
            (case-insensitive) and/or a "password" key if the password fails
            AUTH_PASSWORD_VALIDATORS.

    Called by: PatientRegistrationSerializer.validate() and register_patient().
    """
    errors = {}
    email = User.objects.normalize_email(email)

    if User.objects.filter(email__iexact=email).exists():
        errors["email"] = [DUPLICATE_EMAIL_MESSAGE]

    # Unsaved instance so UserAttributeSimilarityValidator can compare the
    # password against the email and names being registered.
    candidate = User(email=email, first_name=first_name, last_name=last_name)
    try:
        validate_password(password, user=candidate)
    except ValidationError as exc:
        errors["password"] = exc.messages

    if errors:
        raise ValidationError(errors)


@transaction.atomic
def register_patient(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone: str = "",
    date_of_birth: datetime.date | None = None,
    emergency_contact: str = "",
) -> User:
    """Create a patient account: User(role=patient) + Patient profile.

    Both rows are written in one transaction, so a failure creating the
    profile never leaves an orphan User behind. The role is fixed here —
    callers cannot choose it.

    Raises:
        ValidationError: see validate_patient_registration(). Also raised
            with an "email" key when a concurrent request registers the same
            email between the check and the INSERT (unique constraint).
    """
    validate_patient_registration(
        email=email, password=password, first_name=first_name, last_name=last_name
    )

    try:
        # Savepoint: the IntegrityError must not poison the outer transaction.
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=Role.PATIENT,
            )
    except IntegrityError as exc:
        raise ValidationError({"email": [DUPLICATE_EMAIL_MESSAGE]}) from exc

    Patient.objects.create(
        user=user,
        phone=phone,
        date_of_birth=date_of_birth,
        emergency_contact=emergency_contact,
    )
    return user


def ensure_patient_profile(user) -> Patient | None:
    """Give a patient the Patient profile it lacks; other roles get none.

    register_patient() creates the profile on sign-up, but a patient added
    in the admin has none, and booking reads user.patient_profile. Every
    Patient field is optional, so an empty profile is valid. An existing
    profile is returned as it is.
    """
    if not is_patient(user):
        return None
    profile, _ = Patient.objects.get_or_create(user=user)
    return profile
