"""Integration tests for email notifications triggered via API.

Verifies that the correct email is sent when creating, confirming or
cancelling an appointment through the HTTP layer.

Uses locmem email backend (configured in config/settings/test.py).
mail.outbox is cleared before each test by the autouse clear_mail_outbox
fixture in conftest.py.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    TimeSlotFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patient_user(db):
    return UserFactory(role=Role.PATIENT)


@pytest.fixture
def doctor_user(db):
    return UserFactory(role=Role.DOCTOR)


@pytest.fixture
def patient(db, patient_user):
    return PatientFactory(user=patient_user)


@pytest.fixture
def doctor(db, doctor_user):
    return DoctorFactory(user=doctor_user)


@pytest.fixture
def available_slot(db, doctor):
    return TimeSlotFactory(schedule__doctor=doctor)


@pytest.fixture
def auth_client_patient(patient_user):
    client = APIClient()
    client.force_authenticate(user=patient_user)
    return client


@pytest.fixture
def auth_client_doctor(doctor_user):
    client = APIClient()
    client.force_authenticate(user=doctor_user)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAppointmentCreatedEmail:
    def test_creating_appointment_sends_email_to_patient(
        self, auth_client_patient, patient, doctor, available_slot
    ):
        auth_client_patient.post(
            "/api/appointments/",
            {"slot": str(available_slot.id), "reason": "Routine checkup"},
        )
        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to

    def test_no_email_sent_when_booking_fails(
        self, auth_client_patient, patient, doctor, available_slot
    ):
        """If slot is already taken, no email should be sent."""
        available_slot.status = "reserved"
        available_slot.save(update_fields=["status"])

        auth_client_patient.post(
            "/api/appointments/",
            {"slot": str(available_slot.id), "reason": "Checkup"},
        )
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestAppointmentConfirmedEmail:
    def test_confirming_appointment_sends_email_to_patient(
        self, auth_client_doctor, patient, doctor
    ):
        appointment = AppointmentFactory(
            patient=patient, doctor=doctor, status=Appointment.Status.PENDING
        )
        auth_client_doctor.post(f"/api/appointments/{appointment.id}/confirm/")

        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
        assert "confirmed" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
class TestAppointmentCancelledEmail:
    def test_cancelling_appointment_sends_email_to_patient(
        self, auth_client_patient, patient, doctor
    ):
        appointment = AppointmentFactory(
            patient=patient, doctor=doctor, status=Appointment.Status.PENDING
        )
        auth_client_patient.post(f"/api/appointments/{appointment.id}/cancel/")

        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
        assert "cancel" in mail.outbox[0].subject.lower()
