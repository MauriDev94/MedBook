"""Unit tests for notification services.

Tests use the locmem email backend (configured in config/settings/test.py).
All assertions use mail.outbox which is cleared before each test by the
autouse `clear_mail_outbox` fixture in conftest.py.

Paso 37: every email is in the clinic's language (LANGUAGE_CODE, Spanish),
whatever language the request had, and shows the time in Chilean time
(ADR 0003). The API always runs in English (EnglishApiMiddleware), so an
appointment the doctor confirms through the API must still be emailed in
Spanish.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.utils import translation

from apps.doctors.models import Doctor
from apps.notifications.services import (
    send_appointment_cancelled,
    send_appointment_confirmed,
    send_appointment_created,
)
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    TimeSlotFactory,
)

CHILE = ZoneInfo("America/Santiago")
SENDERS = [
    send_appointment_created,
    send_appointment_confirmed,
    send_appointment_cancelled,
]
SUBJECTS = {
    send_appointment_created: "Recibimos tu reserva — MedBook",
    send_appointment_confirmed: "Cita confirmada — MedBook",
    send_appointment_cancelled: "Cita cancelada — MedBook",
}
MESSAGES = {
    send_appointment_created: "Recibimos tu reserva. Te avisaremos cuando la cita"
    " esté confirmada.",
    send_appointment_confirmed: "Tu cita está confirmada. Te recomendamos llegar"
    " 10 minutos antes.",
    send_appointment_cancelled: "Tu cita fue cancelada. Puedes reservar otra hora"
    " en MedBook cuando quieras.",
}


def appointment_at(start, **kwargs):
    """An appointment whose slot starts at `start` (an aware datetime).

    The slot is read back, so its start comes in UTC, as in production.
    """
    slot = TimeSlotFactory(start_datetime=start)
    slot.refresh_from_db()
    kwargs.setdefault("doctor", slot.schedule.doctor)
    return AppointmentFactory(slot=slot, **kwargs)


@pytest.fixture
def appointment(db):
    """Monday 18 January 2027 at 10:00 in Chile, with Dra. Carla Soto."""
    doctor = DoctorFactory(
        title=Doctor.Title.DRA, user__first_name="Carla", user__last_name="Soto"
    )
    patient = PatientFactory(user__first_name="Ana")
    start = datetime.datetime(2027, 1, 18, 10, 0, tzinfo=CHILE)
    return appointment_at(start, doctor=doctor, patient=patient)


@pytest.mark.django_db
@pytest.mark.parametrize("send", SENDERS, ids=lambda send: send.__name__)
class TestEveryEmail:
    def test_sends_one_email_to_the_patient(self, send, appointment):
        send(appointment)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [appointment.patient.user.email]

    def test_subject_and_message_are_in_spanish(self, send, appointment):
        send(appointment)

        assert mail.outbox[0].subject == SUBJECTS[send]
        assert MESSAGES[send] in mail.outbox[0].body

    def test_body_greets_the_patient_and_names_the_doctor(self, send, appointment):
        send(appointment)

        body = mail.outbox[0].body
        assert body.startswith("Hola, Ana:\n")
        assert "Profesional: Dra. Carla Soto\n" in body
        assert body.rstrip().endswith("— MedBook")

    def test_spanish_even_when_the_request_was_in_english(self, send, appointment):
        """The API runs in English; the email follows the clinic, not it."""
        with translation.override("en"):
            send(appointment)
            # The request goes on in its own language
            assert translation.get_language() == "en"

        assert mail.outbox[0].subject == SUBJECTS[send]
        assert "Dra. Carla Soto" in mail.outbox[0].body

    @pytest.mark.parametrize(
        ("start", "moment"),
        [
            (
                datetime.datetime(2027, 1, 18, 10, 0, tzinfo=CHILE),
                "lunes 18 de enero, 10:00 (hora de Chile)",
            ),
            (
                datetime.datetime(2027, 7, 19, 10, 0, tzinfo=CHILE),
                "lunes 19 de julio, 10:00 (hora de Chile)",
            ),
        ],
        ids=["summer-utc-3", "winter-utc-4"],
    )
    def test_time_is_chilean_in_summer_and_winter(self, send, start, moment):
        send(appointment_at(start))

        body = mail.outbox[0].body
        assert f"Fecha y hora: {moment}\n" in body
        assert "UTC" not in body

    def test_patient_without_first_name_gets_a_plain_greeting(self, send):
        start = datetime.datetime(2027, 1, 18, 10, 0, tzinfo=CHILE)
        send(appointment_at(start, patient=PatientFactory(user__first_name="")))

        assert mail.outbox[0].body.startswith("Hola:\n")

    def test_plain_text_is_not_html_escaped(self, send):
        doctor = DoctorFactory(user__first_name="Bernardo", user__last_name="O'Higgins")
        start = datetime.datetime(2027, 1, 18, 10, 0, tzinfo=CHILE)
        send(appointment_at(start, doctor=doctor))

        assert "Dr. Bernardo O'Higgins" in mail.outbox[0].body
