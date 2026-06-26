"""Integration tests for email notifications triggered via API.

Verifies that the correct email is sent when creating, confirming or
cancelling an appointment through the HTTP layer.

Uses locmem email backend (configured in config/settings/test.py).
mail.outbox is cleared before each test by the autouse clear_mail_outbox
fixture in conftest.py.

Appointment services defer notification emails with
transaction.on_commit() (see apps/appointments/services.py) so that an
email failure can never roll back a critical DB write. Because pytest
wraps each test in an atomic block that never commits, on_commit
callbacks don't fire on their own — tests must use the
django_capture_on_commit_callbacks fixture (execute=True) to run them.
"""

import pytest
from django.core import mail
from django.db import transaction
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
        self,
        django_capture_on_commit_callbacks,
        auth_client_patient,
        patient,
        doctor,
        available_slot,
    ):
        with django_capture_on_commit_callbacks(execute=True):
            auth_client_patient.post(
                "/api/v1/appointments/",
                {"slot": str(available_slot.id), "reason": "Routine checkup"},
            )
        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to

    def test_no_email_sent_when_booking_fails(
        self,
        django_capture_on_commit_callbacks,
        auth_client_patient,
        patient,
        doctor,
        available_slot,
    ):
        """If slot is already taken, no email should be sent."""
        available_slot.status = "reserved"
        available_slot.save(update_fields=["status"])

        with django_capture_on_commit_callbacks(execute=True):
            auth_client_patient.post(
                "/api/v1/appointments/",
                {"slot": str(available_slot.id), "reason": "Checkup"},
            )
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestAppointmentConfirmedEmail:
    def test_confirming_appointment_sends_email_to_patient(
        self, django_capture_on_commit_callbacks, auth_client_doctor, patient, doctor
    ):
        appointment = AppointmentFactory(
            patient=patient, doctor=doctor, status=Appointment.Status.PENDING
        )
        with django_capture_on_commit_callbacks(execute=True):
            auth_client_doctor.post(f"/api/v1/appointments/{appointment.id}/confirm/")

        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
        assert "confirmed" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
class TestAppointmentCancelledEmail:
    def test_cancelling_appointment_sends_email_to_patient(
        self, django_capture_on_commit_callbacks, auth_client_patient, patient, doctor
    ):
        appointment = AppointmentFactory(
            patient=patient, doctor=doctor, status=Appointment.Status.PENDING
        )
        with django_capture_on_commit_callbacks(execute=True):
            auth_client_patient.post(f"/api/v1/appointments/{appointment.id}/cancel/")

        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
        assert "cancel" in mail.outbox[0].subject.lower()


@pytest.mark.django_db(transaction=True)
class TestEmailDeferredUntilCommit:
    """Verifies the transaction.on_commit() deferral (issue #75 / audit A1).

    Emails must NOT be sent if the surrounding transaction rolls back —
    an email-sending failure must never be able to roll back a critical
    write either, since the dispatch happens only after a successful
    commit.
    """

    def test_no_email_sent_when_transaction_rolls_back(
        self, auth_client_patient, patient, doctor, available_slot
    ):
        from apps.appointments import services
        from apps.appointments.models import Appointment

        class _ForcedRollback(Exception):
            pass

        with pytest.raises(_ForcedRollback):
            with transaction.atomic():
                services.create_appointment(
                    patient, available_slot, reason="Will be rolled back"
                )
                raise _ForcedRollback("simulate failure after create")

        assert not Appointment.objects.filter(patient=patient).exists()
        assert len(mail.outbox) == 0

    def test_email_sent_when_transaction_commits(
        self,
        django_capture_on_commit_callbacks,
        auth_client_patient,
        patient,
        doctor,
        available_slot,
    ):
        from apps.appointments import services

        with django_capture_on_commit_callbacks(execute=True):
            with transaction.atomic():
                services.create_appointment(
                    patient, available_slot, reason="Commits fine"
                )

        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
