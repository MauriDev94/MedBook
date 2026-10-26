"""Unit tests for apps/users/services.py — patient self-registration.

Business rules under test:
- register_patient() creates a User (role=patient) and its Patient profile
  in a single transaction; any failure leaves no partial records behind.
- Emails are unique case-insensitively ("Ana@x.com" blocks "ana@x.com").
- Passwords go through Django's AUTH_PASSWORD_VALIDATORS.
- Errors are raised as ValidationError keyed by field, so both the API
  serializer and the future web form can map them to field errors.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.patients.models import Patient
from apps.users import services
from apps.users.models import Role, User
from tests.factories import (
    PatientFactory,
    UserFactory,
    random_password,
    short_password,
)

# Generated per run: passes every AUTH_PASSWORD_VALIDATORS check.
REGISTRATION_PHRASE = random_password()


def _register(**overrides):
    data = {
        "email": "ana.perez@example.com",
        "password": REGISTRATION_PHRASE,
        "first_name": "Ana",
        "last_name": "Pérez",
    }
    data.update(overrides)
    return services.register_patient(**data)


@pytest.mark.django_db
class TestRegisterPatient:
    def test_creates_user_with_patient_role(self):
        user = _register()

        assert user.pk is not None
        assert user.role == Role.PATIENT
        assert user.first_name == "Ana"
        assert user.last_name == "Pérez"
        assert user.is_active is True
        assert user.is_staff is False

    def test_creates_linked_patient_profile(self):
        user = _register()

        assert Patient.objects.filter(user=user).exists()

    def test_persists_optional_profile_fields(self):
        user = _register(
            phone="+56912345678",
            date_of_birth=datetime.date(1990, 5, 17),
            emergency_contact="Juan Pérez +56987654321",
        )

        profile = Patient.objects.get(user=user)
        assert profile.phone == "+56912345678"
        assert profile.date_of_birth == datetime.date(1990, 5, 17)
        assert profile.emergency_contact == "Juan Pérez +56987654321"

    def test_optional_profile_fields_default_to_empty(self):
        user = _register()

        profile = Patient.objects.get(user=user)
        assert profile.phone == ""
        assert profile.date_of_birth is None
        assert profile.emergency_contact == ""

    def test_password_is_hashed(self):
        user = _register()

        assert user.password != REGISTRATION_PHRASE
        assert user.check_password(REGISTRATION_PHRASE)

    def test_email_domain_is_normalized(self):
        user = _register(email="Ana.Perez@EXAMPLE.COM")

        assert user.email == "Ana.Perez@example.com"


@pytest.mark.django_db
class TestRegisterPatientValidation:
    def test_duplicate_email_raises_email_error(self):
        UserFactory(email="ana.perez@example.com")

        with pytest.raises(ValidationError) as exc_info:
            _register(email="ana.perez@example.com")

        assert "email" in exc_info.value.message_dict

    def test_duplicate_email_check_is_case_insensitive(self):
        UserFactory(email="ana.perez@example.com")

        with pytest.raises(ValidationError) as exc_info:
            _register(email="ANA.PEREZ@example.com")

        assert "email" in exc_info.value.message_dict

    def test_weak_password_raises_password_error(self):
        with pytest.raises(ValidationError) as exc_info:
            _register(password=short_password())

        assert "password" in exc_info.value.message_dict

    def test_password_similar_to_email_is_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            email = "valentina.soto@example.com"
            _register(email=email, password=email.split("@")[0])

        assert "password" in exc_info.value.message_dict

    def test_reports_email_and_password_errors_together(self):
        UserFactory(email="ana.perez@example.com")

        with pytest.raises(ValidationError) as exc_info:
            _register(email="ana.perez@example.com", password=short_password())

        assert set(exc_info.value.message_dict) == {"email", "password"}

    def test_invalid_registration_creates_nothing(self):
        with pytest.raises(ValidationError):
            _register(password=short_password())

        assert not User.objects.exists()
        assert not Patient.objects.exists()


@pytest.mark.django_db
class TestRegisterPatientAtomicity:
    def test_profile_failure_rolls_back_user(self, monkeypatch):
        def _fail(*args, **kwargs):
            raise IntegrityError("simulated profile failure")

        monkeypatch.setattr(Patient.objects, "create", _fail)

        with pytest.raises(IntegrityError):
            _register()

        assert not User.objects.filter(email="ana.perez@example.com").exists()

    def test_concurrent_duplicate_email_maps_to_email_error(self, monkeypatch):
        """Losing the race between the uniqueness check and the INSERT.

        The pre-check passes, but another request inserted the same email
        first, so the INSERT hits the unique constraint. That must surface
        as the same email error, not as a 500.
        """

        def _race(*args, **kwargs):
            raise IntegrityError("duplicate key value violates unique constraint")

        monkeypatch.setattr(User.objects, "create_user", _race)

        with pytest.raises(ValidationError) as exc_info:
            _register()

        assert "email" in exc_info.value.message_dict


@pytest.mark.django_db
class TestEnsurePatientProfile:
    """A patient created in the admin gets the profile sign-up would create.

    Booking reads request.user.patient_profile; every Patient field is
    optional, so an empty profile is valid.
    """

    def test_creates_an_empty_profile_for_a_patient(self):
        user = UserFactory(role=Role.PATIENT)

        profile = services.ensure_patient_profile(user)

        assert profile.user == user
        assert Patient.objects.filter(user=user).count() == 1

    def test_keeps_an_existing_profile(self):
        patient = PatientFactory(phone="+56912345678")

        profile = services.ensure_patient_profile(patient.user)

        assert profile == patient
        assert profile.phone == "+56912345678"
        assert Patient.objects.count() == 1

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_other_roles_get_none(self, role):
        user = UserFactory(role=role)

        assert services.ensure_patient_profile(user) is None
        assert not Patient.objects.filter(user=user).exists()
