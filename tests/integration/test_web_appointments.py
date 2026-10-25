"""Web "My appointments": list, detail and cancellation (Paso 28).

Patients see their appointments in two tabs: upcoming (not started yet, any
status, so a cancelled one keeps its badge) and past. The list uses the same
visibility rule as the API (appointments_visible_to), so another patient's
appointment is a 404. Cancelling asks first, in a dialog (HTMX) or on a full
page, and calls cancel_appointment: the slot is freed, the email goes out and
the audit line is written. With HTMX the row's status updates in place; an
appointment that can no longer be cancelled never causes a 500.
"""

import datetime
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
    PatientFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)

LIST_URL = "/appointments/"
LIST_TEMPLATE = "web/appointments/list.html"
LIST_PARTIAL = "web/appointments/partials/appointment_list.html"
DETAIL_TEMPLATE = "web/appointments/detail.html"
CANCEL_TEMPLATE = "web/appointments/cancel.html"
CANCEL_PARTIAL = "web/appointments/partials/cancel_dialog.html"
HTMX = {"HX-Request": "true"}
ENGLISH = {"Accept-Language": "en"}
CHILE = ZoneInfo("America/Santiago")

CANNOT_CANCEL = "Esta cita ya no se puede cancelar."


def detail_url(appointment) -> str:
    return f"/appointments/{appointment.pk}/"


def cancel_url(appointment) -> str:
    return f"/appointments/{appointment.pk}/cancel/"


def status_id(appointment) -> str:
    return f"appointment-{appointment.pk}-status"


def days_ahead_at(days, hour, minute=0) -> datetime.datetime:
    day = timezone.localdate() + datetime.timedelta(days=days)
    return datetime.datetime.combine(day, datetime.time(hour, minute), CHILE)


def bare_schedule():
    """A schedule without the slots its post_save signal generated."""
    schedule = ScheduleFactory()
    TimeSlot.objects.filter(schedule=schedule).delete()
    return schedule


def appointment_for(patient, days, hour=10, **kwargs):
    """An appointment of `patient` `days` from today (negative: in the past)."""
    slot = TimeSlotFactory(
        schedule=bare_schedule(),
        start_datetime=days_ahead_at(days, hour),
        status=TimeSlot.Status.RESERVED,
    )
    return AppointmentFactory(
        patient=patient, slot=slot, doctor=slot.schedule.doctor, **kwargs
    )


def weekday_of(appointment) -> str:
    with translation.override("es"):
        start = timezone.localtime(appointment.slot.start_datetime)
        return formats.date_format(start, "l")


@pytest.fixture
def patient(db):
    return PatientFactory()


@pytest.fixture
def patient_client(client, patient):
    client.force_login(patient.user)
    return client


@pytest.fixture
def upcoming(patient):
    """Pending, in two days at 10:00 Chile."""
    return appointment_for(patient, days=2, reason="Control anual")


@pytest.fixture
def past(patient):
    """Completed, two days ago."""
    return appointment_for(patient, days=-2, status=Appointment.Status.COMPLETED)


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestAccess:
    @pytest.mark.parametrize("url", ["list", "detail", "cancel"])
    def test_anonymous_goes_to_login_with_next(self, client, upcoming, url):
        path = {
            "list": LIST_URL,
            "detail": detail_url(upcoming),
            "cancel": cancel_url(upcoming),
        }[url]

        response = client.get(path)

        assert response.status_code == 302
        assert response["Location"] == f"/login/?next={path}"

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_other_roles_are_forbidden(self, client, upcoming, role):
        client.force_login(UserFactory(role=role))

        assert client.get(LIST_URL).status_code == 403
        assert client.get(detail_url(upcoming)).status_code == 403
        assert client.post(cancel_url(upcoming)).status_code == 403
        upcoming.refresh_from_db()
        assert upcoming.status == Appointment.Status.PENDING

    def test_another_patients_appointment_is_404(self, patient_client):
        other = appointment_for(PatientFactory(), days=2)

        assert patient_client.get(detail_url(other)).status_code == 404
        assert patient_client.get(cancel_url(other)).status_code == 404
        assert patient_client.post(cancel_url(other)).status_code == 404
        other.refresh_from_db()
        assert other.status == Appointment.Status.PENDING

    def test_patient_menu_links_to_my_appointments(self, patient_client):
        html = patient_client.get("/").content.decode()

        assert f'href="{LIST_URL}"' in html
        assert "Mis citas" in html


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestList:
    def test_upcoming_is_the_default_tab(self, patient_client, upcoming, past):
        upcoming.doctor.specialties.add(
            SpecialtyFactory(name="Cardiology", slug="cardiology")
        )

        response = patient_client.get(LIST_URL)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, LIST_TEMPLATE)
        assert "Mis citas" in html
        assert detail_url(upcoming) in html
        assert detail_url(past) not in html
        assert str(upcoming.doctor) in html
        assert "Cardiología" in html
        assert weekday_of(upcoming).capitalize() in html
        assert "10:00 – 10:30" in html
        assert "Pendiente" in html

    def test_past_tab(self, patient_client, upcoming, past):
        html = patient_client.get(f"{LIST_URL}?tab=past").content.decode()

        assert detail_url(past) in html
        assert detail_url(upcoming) not in html
        assert "Completada" in html

    def test_unknown_tab_shows_upcoming(self, patient_client, upcoming, past):
        html = patient_client.get(f"{LIST_URL}?tab=nope").content.decode()

        assert detail_url(upcoming) in html
        assert detail_url(past) not in html

    def test_lists_only_the_patients_appointments(self, patient_client, upcoming):
        other = appointment_for(PatientFactory(), days=2)

        html = patient_client.get(LIST_URL).content.decode()

        assert detail_url(upcoming) in html
        assert detail_url(other) not in html

    def test_upcoming_soonest_first(self, patient_client, patient):
        later = appointment_for(patient, days=5)
        sooner = appointment_for(patient, days=1)

        html = patient_client.get(LIST_URL).content.decode()

        assert html.index(detail_url(sooner)) < html.index(detail_url(later))

    def test_past_latest_first(self, patient_client, patient):
        older = appointment_for(patient, days=-5)
        recent = appointment_for(patient, days=-1)

        html = patient_client.get(f"{LIST_URL}?tab=past").content.decode()

        assert html.index(detail_url(recent)) < html.index(detail_url(older))

    def test_cancelled_upcoming_appointment_keeps_its_badge(
        self, patient_client, patient
    ):
        cancelled = appointment_for(
            patient, days=2, status=Appointment.Status.CANCELLED
        )

        html = patient_client.get(LIST_URL).content.decode()

        assert detail_url(cancelled) in html
        assert "Cancelada" in html
        assert cancel_url(cancelled) not in html

    @pytest.mark.parametrize(
        "status", [Appointment.Status.PENDING, Appointment.Status.CONFIRMED]
    )
    def test_upcoming_active_appointment_can_be_cancelled(
        self, patient_client, patient, status
    ):
        appointment = appointment_for(patient, days=2, status=status)

        html = patient_client.get(LIST_URL).content.decode()

        assert f'hx-get="{cancel_url(appointment)}"' in html
        assert 'hx-target="#cancel-dialog"' in html
        assert '<dialog id="cancel-dialog"' in html
        assert "web/js/dialog.js" in html

    def test_past_appointment_has_no_cancel_link(self, patient_client, patient):
        """Even a past appointment the doctor never closed stays read-only."""
        stale = appointment_for(patient, days=-1, status=Appointment.Status.PENDING)

        html = patient_client.get(f"{LIST_URL}?tab=past").content.decode()

        assert detail_url(stale) in html
        assert cancel_url(stale) not in html

    def test_badges_in_english(self, patient_client, upcoming):
        html = patient_client.get(LIST_URL, headers=ENGLISH).content.decode()

        assert "My appointments" in html
        assert "Pending" in html

    def test_no_upcoming_appointments_invites_to_find_a_doctor(
        self, patient_client, past
    ):
        html = patient_client.get(LIST_URL).content.decode()

        assert "No tienes citas próximas." in html
        assert 'href="/doctors/"' in html

    def test_no_past_appointments(self, patient_client, upcoming):
        html = patient_client.get(f"{LIST_URL}?tab=past").content.decode()

        assert "Todavía no tienes citas pasadas." in html

    def test_htmx_tab_switch_gets_only_the_list(self, patient_client, past):
        response = patient_client.get(f"{LIST_URL}?tab=past", headers=HTMX)
        html = response.content.decode()

        assertTemplateUsed(response, LIST_PARTIAL)
        assertTemplateNotUsed(response, LIST_TEMPLATE)
        assert "<html" not in html
        assert 'id="appointment-list"' in html
        assert detail_url(past) in html
        assert "HX-Request" in response["Vary"]

    def test_pagination_keeps_the_tab(self, patient_client, patient):
        for days in range(1, 12):
            appointment_for(patient, days=-days)

        html = patient_client.get(f"{LIST_URL}?tab=past").content.decode()
        page_two = patient_client.get(f"{LIST_URL}?tab=past&page=2").content.decode()

        assert "?tab=past&amp;page=2" in html
        assert "Página 2 de 2" in page_two

    def test_query_count_does_not_grow_with_appointments(
        self, patient_client, patient, django_assert_max_num_queries
    ):
        for days in range(1, 6):
            appointment = appointment_for(patient, days=days)
            appointment.doctor.specialties.add(SpecialtyFactory())

        # session + user, count, page of appointments, specialties
        with django_assert_max_num_queries(5):
            response = patient_client.get(LIST_URL)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestDetail:
    def test_shows_doctor_date_time_status_and_reason(self, patient_client, upcoming):
        response = patient_client.get(detail_url(upcoming))
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, DETAIL_TEMPLATE)
        assert "Detalle de la cita" in html
        assert str(upcoming.doctor) in html
        assert weekday_of(upcoming).capitalize() in html
        assert "10:00 – 10:30" in html
        assert "Pendiente" in html
        assert "Control anual" in html
        assert f'href="{LIST_URL}"' in html

    def test_can_cancel_while_pending(self, patient_client, upcoming):
        html = patient_client.get(detail_url(upcoming)).content.decode()

        assert f'id="{status_id(upcoming)}"' in html
        assert f'hx-get="{cancel_url(upcoming)}"' in html
        assert '<dialog id="cancel-dialog"' in html

    def test_cancelled_appointment_has_no_cancel_link(self, patient_client, patient):
        cancelled = appointment_for(
            patient, days=2, status=Appointment.Status.CANCELLED
        )

        html = patient_client.get(detail_url(cancelled)).content.decode()

        assert "Cancelada" in html
        assert cancel_url(cancelled) not in html

    def test_without_reason(self, patient_client, patient):
        appointment = appointment_for(patient, days=2, reason="")

        html = patient_client.get(detail_url(appointment)).content.decode()

        assert "Sin motivo." in html


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestCancelConfirmation:
    def test_full_page(self, patient_client, upcoming):
        response = patient_client.get(cancel_url(upcoming))
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, CANCEL_TEMPLATE)
        assert "¿Cancelar esta cita?" in html
        assert "10:00 – 10:30" in html
        assert f'action="{cancel_url(upcoming)}"' in html
        assert f'href="{detail_url(upcoming)}"' in html

    def test_htmx_gets_the_dialog_content(self, patient_client, upcoming):
        response = patient_client.get(cancel_url(upcoming), headers=HTMX)
        html = response.content.decode()

        assertTemplateUsed(response, CANCEL_PARTIAL)
        assertTemplateNotUsed(response, CANCEL_TEMPLATE)
        assert "<html" not in html
        assert 'id="cancel-dialog-title"' in html
        assert f'hx-post="{cancel_url(upcoming)}"' in html
        assert 'method="dialog"' in html
        assert "HX-Request" in response["Vary"]

    def test_english(self, patient_client, upcoming):
        html = patient_client.get(cancel_url(upcoming), headers=ENGLISH)

        assert "Cancel this appointment?" in html.content.decode()

    def test_appointment_that_cannot_be_cancelled_goes_back_to_its_page(
        self, patient_client, past
    ):
        response = patient_client.get(cancel_url(past), follow=True)

        assert response.redirect_chain == [(detail_url(past), 302)]
        assert CANNOT_CANCEL in response.content.decode()

    def test_dialog_explains_why_it_cannot_be_cancelled(self, patient_client, past):
        response = patient_client.get(cancel_url(past), headers=HTMX)
        html = response.content.decode()

        assertTemplateUsed(response, CANCEL_PARTIAL)
        assert CANNOT_CANCEL in html
        assert f'hx-post="{cancel_url(past)}"' not in html


@pytest.mark.django_db
class TestCancel:
    def test_cancels_frees_the_slot_sends_the_email_and_logs_it(
        self,
        patient_client,
        patient,
        upcoming,
        caplog,
        django_capture_on_commit_callbacks,
    ):
        with (
            caplog.at_level("INFO", logger="medbook.audit"),
            django_capture_on_commit_callbacks(execute=True),
        ):
            response = patient_client.post(cancel_url(upcoming))

        upcoming.refresh_from_db()
        upcoming.slot.refresh_from_db()
        audit = [r.getMessage() for r in caplog.records if r.name == "medbook.audit"]
        assert response.status_code == 302
        assert response["Location"] == detail_url(upcoming)
        assert upcoming.status == Appointment.Status.CANCELLED
        assert upcoming.slot.status == TimeSlot.Status.AVAILABLE
        assert len(mail.outbox) == 1
        assert patient.user.email in mail.outbox[0].to
        assert any("action=cancel_appointment" in line for line in audit)

    def test_message_names_the_day_and_time(self, patient_client, upcoming):
        response = patient_client.post(cancel_url(upcoming), follow=True)
        html = response.content.decode()

        assert f"Cancelaste tu cita del {weekday_of(upcoming)}" in html
        assert "a las 10:00" in html

    def test_message_in_english(self, patient_client, upcoming):
        response = patient_client.post(
            cancel_url(upcoming), headers=ENGLISH, follow=True
        )

        assert "is cancelled" in response.content.decode()

    def test_htmx_updates_the_status_and_closes_the_dialog(
        self, patient_client, upcoming
    ):
        response = patient_client.post(cancel_url(upcoming), headers=HTMX)
        html = response.content.decode()

        assert response.status_code == 200
        assert response["HX-Retarget"] == f"#{status_id(upcoming)}"
        assert response["HX-Reswap"] == "outerHTML"
        assert f'id="{status_id(upcoming)}"' in html
        assert "Cancelada" in html
        assert cancel_url(upcoming) not in html
        assert 'id="messages" hx-swap-oob="true"' in html
        assert "Cancelaste tu cita" in html

    def test_pages_always_have_the_messages_region(self, patient_client, upcoming):
        """The HTMX response swaps its message into it (hx-swap-oob)."""
        html = patient_client.get(detail_url(upcoming)).content.decode()

        assert 'id="messages"' in html

    def test_completed_appointment_is_not_cancelled(self, patient_client, past):
        response = patient_client.post(cancel_url(past), follow=True)

        past.refresh_from_db()
        assert response.redirect_chain == [(detail_url(past), 302)]
        assert past.status == Appointment.Status.COMPLETED
        assert CANNOT_CANCEL in response.content.decode()
        assert len(mail.outbox) == 0

    def test_already_cancelled_in_the_dialog(self, patient_client, upcoming):
        """Cancelled elsewhere while the dialog was open: say so, show the status."""
        upcoming.status = Appointment.Status.CANCELLED
        upcoming.save(update_fields=["status", "updated_at"])

        response = patient_client.post(cancel_url(upcoming), headers=HTMX)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, CANCEL_PARTIAL)
        assert CANNOT_CANCEL in html
        assert f'id="{status_id(upcoming)}" hx-swap-oob="true"' in html
        assert "Cancelada" in html

    def test_post_needs_the_csrf_token(self, patient, upcoming):
        client = Client(enforce_csrf_checks=True)
        client.force_login(patient.user)

        response = client.post(cancel_url(upcoming))

        upcoming.refresh_from_db()
        assert response.status_code == 403
        assert upcoming.status == Appointment.Status.PENDING
