"""Web forms: sign-up (Paso 25) and booking (Paso 27).

The forms validate the format and delegate the business rules (unique
email, password policy, bookable slot) to the services, like the API
serializers. Errors come out in the active language: Spanish unless told
otherwise.
"""

import pytest
from django.utils import translation

from apps.appointments.models import TimeSlot
from apps.web.forms import BookingForm, SignupForm
from tests.factories import (
    AppointmentFactory,
    PatientFactory,
    TimeSlotFactory,
    UserFactory,
    random_password,
    short_password,
)

# Generated per run, never hardcoded
PASSPHRASE = random_password()


def form_data(**overrides):
    data = {
        "first_name": "Ana",
        "last_name": "Rojas",
        "email": "ana@example.com",
        "password": PASSPHRASE,
        "password_confirm": PASSPHRASE,
    }
    return {**data, **overrides}


@pytest.mark.django_db
class TestSignupForm:
    def test_valid_data(self):
        assert SignupForm(data=form_data()).is_valid()

    def test_registration_data_is_what_the_service_takes(self):
        form = SignupForm(data=form_data())
        form.is_valid()

        assert form.registration_data() == {
            "first_name": "Ana",
            "last_name": "Rojas",
            "email": "ana@example.com",
            "password": PASSPHRASE,
        }

    @pytest.mark.parametrize("field", ["first_name", "last_name", "email"])
    def test_required_fields(self, field):
        form = SignupForm(data=form_data(**{field: ""}))

        assert not form.is_valid()
        assert field in form.errors

    def test_passwords_must_match(self):
        form = SignupForm(data=form_data(password_confirm=random_password()))

        assert not form.is_valid()
        assert form.errors["password_confirm"] == ["Las contraseñas no coinciden."]

    def test_duplicate_email_is_a_field_error_in_spanish(self):
        UserFactory(email="ana@example.com")

        form = SignupForm(data=form_data(email="ANA@example.com"))

        assert not form.is_valid()
        assert form.errors["email"] == ["Ya existe un usuario con este correo."]

    def test_duplicate_email_in_english_when_active(self):
        UserFactory(email="ana@example.com")

        with translation.override("en"):
            form = SignupForm(data=form_data())
            assert not form.is_valid()
            assert form.errors["email"] == ["A user with this email already exists."]

    def test_weak_password_is_a_field_error_in_spanish(self):
        weak = short_password()

        form = SignupForm(data=form_data(password=weak, password_confirm=weak))

        assert not form.is_valid()
        assert any("demasiado corta" in e for e in form.errors["password"])


@pytest.mark.django_db
class TestBookingForm:
    def test_reason_is_optional(self):
        form = BookingForm(data={}, patient=PatientFactory(), slot=TimeSlotFactory())

        assert form.is_valid()
        assert form.cleaned_data["reason"] == ""

    def test_unavailable_slot_is_a_form_error_in_spanish(self):
        slot = TimeSlotFactory(status=TimeSlot.Status.RESERVED)

        form = BookingForm(data={}, patient=PatientFactory(), slot=slot)

        assert not form.is_valid()
        assert form.non_field_errors() == ["Esta hora ya no está disponible."]

    def test_overlap_is_a_form_error_in_english_when_active(self):
        patient = PatientFactory()
        slot = TimeSlotFactory()
        AppointmentFactory(
            patient=patient, slot=TimeSlotFactory(start_datetime=slot.start_datetime)
        )

        with translation.override("en"):
            form = BookingForm(data={}, patient=patient, slot=slot)
            assert not form.is_valid()
            assert form.non_field_errors() == [
                "You already have an appointment at this time."
            ]
