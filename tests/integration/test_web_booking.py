"""Web booking: confirm a slot and book it (Paso 27).

A slot on the doctor's page opens a dialog that HTMX fills with the booking
form; without JavaScript the same URL is a full confirmation page. Booking
calls the same services as the API (validate_appointment_booking, then
create_appointment with its atomic reservation). Success goes to "My
appointments" with a message (Paso 28). A slot that can no longer be booked
never causes a 500: the full page goes back to the doctor's page, on the
slot's week, with the reason, and the dialog shows it and refreshes the week
behind it.
"""

import datetime
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.test import Client
from django.utils import formats, timezone, translation
from pytest_django.asserts import assertTemplateNotUsed, assertTemplateUsed

from apps.appointments.models import Appointment, TimeSlot
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)

PAGE_TEMPLATE = "web/booking/confirm.html"
DIALOG_PARTIAL = "web/booking/partials/dialog.html"
MY_APPOINTMENTS = "/appointments/"
HTMX = {"HX-Request": "true"}
ENGLISH = {"Accept-Language": "en"}
CHILE = ZoneInfo("America/Santiago")

UNAVAILABLE = "Esta hora ya no está disponible."
STARTED = "Esta hora ya empezó."
OVERLAP = "Ya tienes una cita que se cruza con esta hora."
TAKEN = "Otro paciente acaba de reservar esta hora."


def book_url(slot) -> str:
    return f"/slots/{slot.pk}/book/"


def doctor_url(slot, week=0) -> str:
    return f"/doctors/{slot.schedule.doctor.pk}/?week={week}"


def days_ahead_at(days, hour, minute=0) -> datetime.datetime:
    day = timezone.localdate() + datetime.timedelta(days=days)
    return datetime.datetime.combine(day, datetime.time(hour, minute), CHILE)


@pytest.fixture
def patient(db):
    return PatientFactory()


@pytest.fixture
def patient_client(client, patient):
    client.force_login(patient.user)
    return client


def bare_schedule(**kwargs):
    """A schedule without the slots its post_save signal generated."""
    schedule = ScheduleFactory(**kwargs)
    TimeSlot.objects.filter(schedule=schedule).delete()
    return schedule


@pytest.fixture
def schedule(db):
    return bare_schedule()


@pytest.fixture
def slot(schedule):
    """Available, tomorrow at 10:00 in Chile: the current booking week."""
    return TimeSlotFactory(schedule=schedule, start_datetime=days_ahead_at(1, 10))


def reserve(slot) -> None:
    slot.status = TimeSlot.Status.RESERVED
    slot.save(update_fields=["status", "updated_at"])


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBookingAccess:
    def test_anonymous_goes_to_login_with_next(self, client, slot):
        response = client.get(book_url(slot))

        assert response.status_code == 302
        assert response["Location"] == f"/login/?next={book_url(slot)}"

    def test_anonymous_post_books_nothing(self, client, slot):
        response = client.post(book_url(slot))

        assert response.status_code == 302
        assert not Appointment.objects.exists()

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_other_roles_are_forbidden(self, client, slot, role):
        client.force_login(UserFactory(role=role))

        assert client.get(book_url(slot)).status_code == 403
        assert client.post(book_url(slot)).status_code == 403
        assert not Appointment.objects.exists()

    def test_unknown_slot_is_404(self, patient_client):
        response = patient_client.get(f"/slots/{uuid.uuid4()}/book/")

        assert response.status_code == 404

    def test_slot_of_an_inactive_doctor_is_404(self, patient_client):
        doctor = DoctorFactory(user=UserFactory(role=Role.DOCTOR, is_active=False))
        slot = TimeSlotFactory(
            schedule=bare_schedule(doctor=doctor), start_datetime=days_ahead_at(1, 10)
        )

        assert patient_client.get(book_url(slot)).status_code == 404
        assert patient_client.post(book_url(slot)).status_code == 404

    def test_post_needs_the_csrf_token(self, patient, slot):
        client = Client(enforce_csrf_checks=True)
        client.force_login(patient.user)

        response = client.post(book_url(slot))

        assert response.status_code == 403
        assert not Appointment.objects.exists()


# ---------------------------------------------------------------------------
# Confirmation: full page (no JavaScript) and dialog (HTMX)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestConfirmation:
    def test_full_page_shows_doctor_date_and_chilean_time(self, patient_client, slot):
        doctor = slot.schedule.doctor
        doctor.specialties.add(SpecialtyFactory(name="Cardiology", slug="cardiology"))

        response = patient_client.get(book_url(slot))
        html = response.content.decode()

        with translation.override("es"):
            weekday = formats.date_format(timezone.localtime(slot.start_datetime), "l")
        assert response.status_code == 200
        assertTemplateUsed(response, PAGE_TEMPLATE)
        assert "Confirma tu hora" in html
        assert str(doctor) in html
        assert "Cardiología" in html
        assert weekday.capitalize() in html
        assert "10:00 – 10:30" in html
        assert "hora de Chile" in html
        assert 'name="reason"' in html
        assert f'href="/doctors/{doctor.pk}/"' in html

    def test_htmx_gets_the_dialog_content(self, patient_client, slot):
        response = patient_client.get(book_url(slot), headers=HTMX)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, DIALOG_PARTIAL)
        assertTemplateNotUsed(response, PAGE_TEMPLATE)
        assert "<html" not in html
        assert 'id="booking-dialog-title"' in html
        assert f'hx-post="{book_url(slot)}"' in html
        assert 'method="dialog"' in html
        assert "10:00 – 10:30" in html

    def test_response_varies_on_hx_request(self, patient_client, slot):
        response = patient_client.get(book_url(slot))

        assert "HX-Request" in response["Vary"]

    def test_english_page(self, patient_client, slot):
        response = patient_client.get(book_url(slot), headers=ENGLISH)
        html = response.content.decode()

        assert "Confirm your appointment" in html
        assert "Chilean time" in html

    def test_unbookable_slot_sends_the_page_back_to_the_doctor(
        self, patient_client, slot
    ):
        reserve(slot)

        response = patient_client.get(book_url(slot))

        assert response.status_code == 302
        assert response["Location"] == doctor_url(slot)
        assert UNAVAILABLE in patient_client.get(doctor_url(slot)).content.decode()

    def test_unbookable_slot_in_the_dialog_explains_and_refreshes_the_week(
        self, patient_client, slot, schedule
    ):
        reserve(slot)
        other = TimeSlotFactory(schedule=schedule, start_datetime=days_ahead_at(1, 11))

        response = patient_client.get(book_url(slot), headers=HTMX)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, DIALOG_PARTIAL)
        assert UNAVAILABLE in html
        assert 'name="reason"' not in html
        assert 'id="week-slots" hx-swap-oob="true"' in html
        assert book_url(other) in html
        assert book_url(slot) not in html

    def test_query_count_is_bounded(
        self, patient_client, slot, django_assert_max_num_queries
    ):
        slot.schedule.doctor.specialties.add(SpecialtyFactory(slug="cardiology"))

        # session + user, patient, slot + doctor + user, specialties, overlap check
        with django_assert_max_num_queries(6):
            response = patient_client.get(book_url(slot))

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBooking:
    def test_books_the_slot_and_sends_the_email(
        self, patient_client, patient, slot, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = patient_client.post(book_url(slot), {"reason": "Control anual"})

        appointment = Appointment.objects.get(slot=slot)
        slot.refresh_from_db()
        assert response.status_code == 302
        assert response["Location"] == MY_APPOINTMENTS
        assert appointment.patient == patient
        assert appointment.doctor == slot.schedule.doctor
        assert appointment.status == Appointment.Status.PENDING
        assert appointment.reason == "Control anual"
        assert slot.status == TimeSlot.Status.RESERVED
        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to

    def test_reason_is_optional(self, patient_client, slot):
        patient_client.post(book_url(slot))

        assert Appointment.objects.get(slot=slot).reason == ""

    def test_success_message_names_the_day_and_time(self, patient_client, slot):
        response = patient_client.post(book_url(slot), follow=True)
        html = response.content.decode()

        with translation.override("es"):
            weekday = formats.date_format(timezone.localtime(slot.start_datetime), "l")
        assert f"Reservaste tu hora del {weekday}" in html
        assert "a las 10:00. Te enviamos un correo con el detalle." in html

    def test_success_message_in_english(self, patient_client, slot):
        response = patient_client.post(book_url(slot), headers=ENGLISH, follow=True)

        assert "at 10:00 is booked." in response.content.decode()

    def test_lands_on_my_appointments_with_the_new_one(self, patient_client, slot):
        response = patient_client.post(book_url(slot), follow=True)

        appointment = Appointment.objects.get(slot=slot)
        assert response.redirect_chain == [(MY_APPOINTMENTS, 302)]
        assert f"/appointments/{appointment.pk}/" in response.content.decode()

    def test_booked_slot_leaves_the_doctors_page(self, patient_client, slot):
        patient_client.post(book_url(slot))

        html = patient_client.get(doctor_url(slot)).content.decode()

        assert book_url(slot) not in html

    def test_htmx_success_loads_my_appointments(self, patient_client, slot):
        response = patient_client.post(book_url(slot), headers=HTMX)

        assert response.status_code == 200
        assert response["HX-Redirect"] == MY_APPOINTMENTS
        assert Appointment.objects.filter(slot=slot).exists()


@pytest.mark.django_db
class TestBookingFailures:
    """Nothing is booked, the reason is shown and there is never a 500."""

    def test_slot_taken_before_confirming(self, patient_client, slot):
        reserve(slot)

        response = patient_client.post(book_url(slot), follow=True)

        assert response.redirect_chain == [(doctor_url(slot), 302)]
        assert UNAVAILABLE in response.content.decode()
        assert not Appointment.objects.exists()

    def test_failure_returns_to_the_week_of_the_slot(self, patient_client, schedule):
        next_week = TimeSlotFactory(
            schedule=schedule, start_datetime=days_ahead_at(8, 10)
        )
        reserve(next_week)

        response = patient_client.post(book_url(next_week))

        assert response["Location"] == doctor_url(next_week, week=1)

    def test_slot_that_already_started(self, patient_client, schedule):
        started = TimeSlotFactory(
            schedule=schedule,
            start_datetime=timezone.now() - datetime.timedelta(minutes=5),
        )

        response = patient_client.post(book_url(started), follow=True)

        assert STARTED in response.content.decode()
        assert not Appointment.objects.exists()

    def test_overlapping_appointment(self, patient_client, patient, slot, schedule):
        other_doctor_slot = TimeSlotFactory(
            schedule=bare_schedule(), start_datetime=slot.start_datetime
        )
        AppointmentFactory(patient=patient, slot=other_doctor_slot)

        response = patient_client.post(book_url(slot), follow=True)

        assert OVERLAP in response.content.decode()
        assert not Appointment.objects.filter(slot=slot).exists()

    def test_failure_in_the_dialog_explains_and_refreshes_the_week(
        self, patient_client, slot
    ):
        reserve(slot)

        response = patient_client.post(book_url(slot), headers=HTMX)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, DIALOG_PARTIAL)
        assert UNAVAILABLE in html
        assert 'hx-swap-oob="true"' in html
        assert not Appointment.objects.exists()

    def test_another_patient_wins_the_race(self, patient_client, slot, monkeypatch):
        """The check passes, then the atomic reservation finds the slot taken."""
        monkeypatch.setattr(
            "apps.web.forms.validate_appointment_booking", lambda patient, slot: None
        )
        reserve(slot)

        page = patient_client.post(book_url(slot), follow=True)
        dialog = patient_client.post(book_url(slot), headers=HTMX)

        assert TAKEN in page.content.decode()
        assert TAKEN in dialog.content.decode()
        assert 'hx-swap-oob="true"' in dialog.content.decode()
        assert not Appointment.objects.exists()

    def test_race_message_in_english(self, patient_client, slot, monkeypatch):
        monkeypatch.setattr(
            "apps.web.forms.validate_appointment_booking", lambda patient, slot: None
        )
        reserve(slot)

        response = patient_client.post(book_url(slot), headers=ENGLISH, follow=True)

        assert "Another patient just booked this time." in response.content.decode()
