"""Unit tests for notification services.

Tests use the locmem email backend (configured in config/settings/test.py).
All assertions use mail.outbox which is cleared before each test by the
autouse `clear_mail_outbox` fixture in conftest.py.
"""

import pytest
from django.core import mail

from apps.notifications.services import (
    send_appointment_cancelled,
    send_appointment_confirmed,
    send_appointment_created,
)
from tests.factories import AppointmentFactory


@pytest.mark.django_db
class TestSendAppointmentCreated:
    def test_sends_one_email(self):
        appointment = AppointmentFactory()
        send_appointment_created(appointment)
        assert len(mail.outbox) == 1

    def test_recipient_is_patient_email(self):
        appointment = AppointmentFactory()
        send_appointment_created(appointment)
        assert appointment.patient.user.email in mail.outbox[0].to

    def test_subject_mentions_booking(self):
        appointment = AppointmentFactory()
        send_appointment_created(appointment)
        subject = mail.outbox[0].subject.lower()
        assert "booking" in subject or "received" in subject or "appointment" in subject

    def test_body_contains_doctor_name(self):
        appointment = AppointmentFactory()
        send_appointment_created(appointment)
        doctor = appointment.doctor.user
        doctor_name = doctor.full_name or doctor.email
        assert doctor_name in mail.outbox[0].body

    def test_body_contains_slot_date(self):
        appointment = AppointmentFactory()
        send_appointment_created(appointment)
        year = str(appointment.slot.start_datetime.year)
        assert year in mail.outbox[0].body


@pytest.mark.django_db
class TestSendAppointmentConfirmed:
    def test_sends_one_email(self):
        appointment = AppointmentFactory(status="confirmed")
        send_appointment_confirmed(appointment)
        assert len(mail.outbox) == 1

    def test_recipient_is_patient_email(self):
        appointment = AppointmentFactory(status="confirmed")
        send_appointment_confirmed(appointment)
        assert appointment.patient.user.email in mail.outbox[0].to

    def test_subject_mentions_confirmed(self):
        appointment = AppointmentFactory(status="confirmed")
        send_appointment_confirmed(appointment)
        assert "confirmed" in mail.outbox[0].subject.lower()

    def test_body_contains_doctor_name(self):
        appointment = AppointmentFactory(status="confirmed")
        send_appointment_confirmed(appointment)
        doctor = appointment.doctor.user
        doctor_name = doctor.full_name or doctor.email
        assert doctor_name in mail.outbox[0].body


@pytest.mark.django_db
class TestSendAppointmentCancelled:
    def test_sends_one_email(self):
        appointment = AppointmentFactory(status="cancelled")
        send_appointment_cancelled(appointment)
        assert len(mail.outbox) == 1

    def test_recipient_is_patient_email(self):
        appointment = AppointmentFactory(status="cancelled")
        send_appointment_cancelled(appointment)
        assert appointment.patient.user.email in mail.outbox[0].to

    def test_subject_mentions_cancelled(self):
        appointment = AppointmentFactory(status="cancelled")
        send_appointment_cancelled(appointment)
        assert "cancel" in mail.outbox[0].subject.lower()

    def test_body_contains_slot_date(self):
        appointment = AppointmentFactory(status="cancelled")
        send_appointment_cancelled(appointment)
        year = str(appointment.slot.start_datetime.year)
        assert year in mail.outbox[0].body
