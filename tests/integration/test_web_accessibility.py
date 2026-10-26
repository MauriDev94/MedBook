"""Accessibility of the web UI (Paso 29).

- A skip link jumps over the menu to the main content.
- `#live-status` is an empty, polite live region in the layout. Every
  HTMX response that swaps a list (doctors, a week of slots, appointments)
  fills it out of band with a short summary, so a screen reader hears what
  changed while the focus stays where it was. `innerHTML` keeps the region's
  node: a replaced live region is often not announced.
- Repeated links carry hidden context: which doctor, which day.
- The week, tab and page links sit inside the content they replace. Each
  carries a fixed id: when the focused element is swapped away, htmx
  focuses the element with the same id in the new content, so the focus
  stays on the link the visitor used instead of dropping to <body>.
- After cancelling, dialog.js moves the focus to the appointment's status,
  so the status block must be focusable.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import formats, timezone, translation

from apps.appointments.models import TimeSlot
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    ScheduleFactory,
    TimeSlotFactory,
)

HTMX = {"HX-Request": "true"}
ENGLISH = {"Accept-Language": "en"}
CHILE = ZoneInfo("America/Santiago")
LIVE_REGION = (
    '<p id="live-status" class="sr-only" aria-live="polite" aria-atomic="true"></p>'
)
LIVE_UPDATE = 'id="live-status" hx-swap-oob="innerHTML"'


def days_ahead_at(days, hour) -> datetime.datetime:
    day = timezone.localdate() + datetime.timedelta(days=days)
    return datetime.datetime.combine(day, datetime.time(hour), CHILE)


@pytest.fixture
def patient(db):
    return PatientFactory()


@pytest.fixture
def patient_client(client, patient):
    client.force_login(patient.user)
    return client


@pytest.fixture
def schedule(db):
    """A schedule without the slots its post_save signal generated."""
    schedule = ScheduleFactory()
    TimeSlot.objects.filter(schedule=schedule).delete()
    return schedule


def slot_in(schedule, days, hour):
    start = days_ahead_at(days, hour)
    return TimeSlotFactory(
        schedule=schedule,
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=30),
    )


class TestLayout:
    def test_skip_link_jumps_to_the_main_content(self, client):
        html = client.get("/").content.decode()

        assert '<a href="#main"' in html
        assert "Saltar al contenido" in html
        assert '<main id="main"' in html

    def test_live_region_starts_empty(self, client):
        html = client.get("/").content.decode()

        assert LIVE_REGION in html
        assert LIVE_UPDATE not in html


@pytest.mark.django_db
class TestDoctorListSummary:
    def test_htmx_filter_announces_how_many_doctors(self, patient_client):
        DoctorFactory.create_batch(2)

        html = patient_client.get("/doctors/", headers=HTMX).content.decode()

        assert LIVE_UPDATE in html
        assert "Se encontraron 2 médicos." in html

    def test_one_doctor(self, patient_client):
        DoctorFactory()

        html = patient_client.get("/doctors/", headers=HTMX).content.decode()

        assert "Se encontró 1 médico." in html

    def test_names_the_page_when_paginated(self, patient_client):
        DoctorFactory.create_batch(11)

        html = patient_client.get(
            "/doctors/", {"page": 2}, headers=HTMX
        ).content.decode()

        assert "Se encontraron 11 médicos. Página 2 de 2." in html

    def test_english(self, patient_client):
        DoctorFactory.create_batch(2)

        html = patient_client.get(
            "/doctors/", headers={**HTMX, **ENGLISH}
        ).content.decode()

        assert "2 doctors found." in html

    def test_full_page_leaves_the_region_empty(self, patient_client):
        DoctorFactory()

        html = patient_client.get("/doctors/").content.decode()

        assert LIVE_REGION in html
        assert LIVE_UPDATE not in html

    def test_history_restore_leaves_the_region_empty(self, patient_client):
        """The restore gets the full page, which already has the region."""
        headers = {**HTMX, "HX-History-Restore-Request": "true"}

        html = patient_client.get("/doctors/", headers=headers).content.decode()

        assert LIVE_UPDATE not in html

    def test_see_times_link_names_the_doctor(self, patient_client):
        doctor = DoctorFactory(user__first_name="Carla", user__last_name="Soto")

        html = patient_client.get("/doctors/").content.decode()

        assert f'<span class="sr-only">: {doctor}</span>' in html


@pytest.mark.django_db
class TestWeekSummary:
    def test_htmx_week_announces_dates_and_times(self, patient_client, schedule):
        slot_in(schedule, days=8, hour=10)
        slot_in(schedule, days=9, hour=11)

        html = patient_client.get(
            f"/doctors/{schedule.doctor.pk}/", {"week": 1}, headers=HTMX
        ).content.decode()

        assert LIVE_UPDATE in html
        assert "2 horas disponibles." in html

    def test_empty_week(self, patient_client, schedule):
        html = patient_client.get(
            f"/doctors/{schedule.doctor.pk}/", {"week": 1}, headers=HTMX
        ).content.decode()

        assert LIVE_UPDATE in html
        assert "No hay horas disponibles esta semana." in html

    def test_full_page_leaves_the_region_empty(self, patient_client, schedule):
        html = patient_client.get(f"/doctors/{schedule.doctor.pk}/").content.decode()

        assert LIVE_UPDATE not in html

    def test_slot_link_names_its_day(self, patient_client, schedule):
        """A list of links read on its own says "Monday, October 27, 10:00"."""
        slot_in(schedule, days=1, hour=10)
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        with translation.override("es"):
            weekday = formats.date_format(tomorrow, "l")
            date = formats.date_format(tomorrow, "MONTH_DAY_FORMAT")

        html = patient_client.get(f"/doctors/{schedule.doctor.pk}/").content.decode()

        assert f'<span class="sr-only">{weekday} {date}, </span>' in html


@pytest.mark.django_db
class TestAppointmentListSummary:
    def test_htmx_tab_announces_how_many(self, patient_client, patient, schedule):
        slot = slot_in(schedule, days=2, hour=10)
        AppointmentFactory(patient=patient, slot=slot, doctor=schedule.doctor)

        html = patient_client.get("/appointments/", headers=HTMX).content.decode()

        assert LIVE_UPDATE in html
        assert "1 cita próxima." in html

    def test_past_tab(self, patient_client):
        html = patient_client.get(
            "/appointments/", {"tab": "past"}, headers=HTMX
        ).content.decode()

        assert "0 citas pasadas." in html

    def test_full_page_leaves_the_region_empty(self, patient_client):
        html = patient_client.get("/appointments/").content.decode()

        assert LIVE_UPDATE not in html


@pytest.mark.django_db
class TestFocusAfterSwaps:
    def test_week_links(self, patient_client, schedule):
        html = patient_client.get(
            f"/doctors/{schedule.doctor.pk}/", {"week": 1}, headers=HTMX
        ).content.decode()

        assert '<a id="week-previous" href="?week=0"' in html
        assert '<a id="week-next" href="?week=2"' in html

    def test_appointment_tabs(self, patient_client):
        html = patient_client.get("/appointments/", headers=HTMX).content.decode()

        assert 'id="tab-upcoming"' in html
        assert 'id="tab-past"' in html

    def test_appointment_pages(self, patient_client, patient, schedule):
        for days in range(1, 12):
            slot = slot_in(schedule, days=days, hour=10)
            AppointmentFactory(patient=patient, slot=slot, doctor=schedule.doctor)

        first = patient_client.get("/appointments/", headers=HTMX).content.decode()
        second = patient_client.get(
            "/appointments/", {"page": 2}, headers=HTMX
        ).content.decode()

        assert 'id="appointments-next"' in first
        assert 'id="appointments-previous"' in second

    def test_doctor_pages(self, patient_client):
        DoctorFactory.create_batch(11)

        first = patient_client.get("/doctors/", headers=HTMX).content.decode()
        second = patient_client.get(
            "/doctors/", {"page": 2}, headers=HTMX
        ).content.decode()

        assert 'id="doctors-next"' in first
        assert 'id="doctors-previous"' in second


@pytest.mark.django_db
class TestFocusAfterCancelling:
    def test_status_block_can_take_the_focus(self, patient_client, patient, schedule):
        slot = slot_in(schedule, days=2, hour=10)
        appointment = AppointmentFactory(
            patient=patient, slot=slot, doctor=schedule.doctor
        )

        html = patient_client.get("/appointments/").content.decode()

        assert f'id="appointment-{appointment.pk}-status" tabindex="-1"' in html
