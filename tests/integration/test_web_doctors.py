"""Web doctor catalog: list with specialty filter and detail with slots (Paso 26).

Patients only: anonymous visitors go to the login page with `?next=`, and
doctors and admins get 403. An HTMX request gets just the fragment it swaps
(the doctor list, or one week of slots); any other request gets the full
page. Slots are the available ones that have not started yet, shown in
Chilean time (ADR 0003).
"""

import datetime
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from pytest_django.asserts import assertTemplateNotUsed, assertTemplateUsed

from apps.appointments.models import TimeSlot
from apps.users.models import Role
from apps.web.views import DoctorListView
from tests.factories import (
    DoctorFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)

LIST_URL = "/doctors/"
LIST_TEMPLATE = "web/doctors/list.html"
LIST_PARTIAL = "web/doctors/partials/doctor_list.html"
DETAIL_TEMPLATE = "web/doctors/detail.html"
WEEK_PARTIAL = "web/doctors/partials/week_slots.html"
HTMX = {"HX-Request": "true"}
CHILE = ZoneInfo("America/Santiago")


def detail_url(doctor) -> str:
    return f"/doctors/{doctor.pk}/"


def tomorrow_at(hour, minute=0) -> datetime.datetime:
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    return datetime.datetime.combine(tomorrow, datetime.time(hour, minute), CHILE)


@pytest.fixture
def patient_client(client):
    client.force_login(UserFactory(role=Role.PATIENT))
    return client


@pytest.fixture
def schedule(db):
    """A schedule without the slots its post_save signal generated."""
    schedule = ScheduleFactory()
    TimeSlot.objects.filter(schedule=schedule).delete()
    return schedule


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestCatalogAccess:
    def test_anonymous_list_goes_to_login(self, client):
        response = client.get(LIST_URL)

        assert response.status_code == 302
        assert response["Location"] == "/login/?next=/doctors/"

    def test_anonymous_detail_goes_to_login_with_next(self, client):
        doctor = DoctorFactory()

        response = client.get(detail_url(doctor))

        assert response.status_code == 302
        assert response["Location"] == f"/login/?next=/doctors/{doctor.pk}/"

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_other_roles_are_forbidden(self, client, role):
        doctor = DoctorFactory()
        client.force_login(UserFactory(role=role))

        assert client.get(LIST_URL).status_code == 403
        assert client.get(detail_url(doctor)).status_code == 403

    def test_patient_sees_catalog_link_in_layout(self, patient_client):
        response = patient_client.get("/")

        assert f'href="{LIST_URL}"' in response.content.decode()

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_staff_layout_has_no_catalog_link(self, client, role):
        client.force_login(UserFactory(role=role))

        response = client.get("/")

        assert f'href="{LIST_URL}"' not in response.content.decode()


# ---------------------------------------------------------------------------
# Doctor list
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestDoctorList:
    def test_full_page_lists_doctors_and_specialties(self, patient_client):
        cardiology = SpecialtyFactory(name="Cardiology", slug="cardiology")
        doctor = DoctorFactory(user__last_name="Araya", specialties=[cardiology])

        response = patient_client.get(LIST_URL)
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, LIST_TEMPLATE)
        assertTemplateUsed(response, "web/base.html")
        assert "Araya" in html
        assert "Cardiología" in html
        assert detail_url(doctor) in html

    def test_filter_offers_every_specialty(self, patient_client):
        slugs = ("cardiology", "dermatology", "pediatrics")
        for slug in slugs:
            SpecialtyFactory(slug=slug)

        response = patient_client.get(LIST_URL)
        html = response.content.decode()

        for slug in slugs:
            assert f'value="{slug}"' in html

    def test_filter_by_specialty(self, patient_client):
        cardiology = SpecialtyFactory(slug="cardiology")
        DoctorFactory(user__last_name="Araya", specialties=[cardiology])
        DoctorFactory(
            user__last_name="Soto",
            specialties=[SpecialtyFactory(slug="dermatology")],
        )

        response = patient_client.get(LIST_URL, {"specialty": "cardiology"})
        html = response.content.decode()

        assert "Araya" in html
        assert "Soto" not in html
        assert '<option value="cardiology" selected>' in html

    def test_htmx_filter_returns_only_the_list(self, patient_client):
        cardiology = SpecialtyFactory(slug="cardiology")
        DoctorFactory(user__last_name="Araya", specialties=[cardiology])

        response = patient_client.get(
            LIST_URL, {"specialty": "cardiology"}, headers=HTMX
        )
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, LIST_PARTIAL)
        assertTemplateNotUsed(response, "web/base.html")
        assert 'id="doctor-list"' in html
        assert "Araya" in html
        assert "<html" not in html

    def test_htmx_history_restore_gets_the_full_page(self, patient_client):
        """HTMX re-fetches a page it has no snapshot of; it needs the layout."""
        response = patient_client.get(
            LIST_URL, headers={**HTMX, "HX-History-Restore-Request": "true"}
        )

        assertTemplateUsed(response, "web/base.html")

    def test_response_varies_on_hx_request(self, patient_client):
        response = patient_client.get(LIST_URL)

        assert "HX-Request" in response["Vary"]

    def test_empty_specialty_shows_empty_state(self, patient_client):
        DoctorFactory(specialties=[SpecialtyFactory(slug="dermatology")])

        response = patient_client.get(LIST_URL, {"specialty": "neurology"})

        assert "No hay médicos para esta especialidad." in response.content.decode()

    def test_inactive_doctor_is_not_listed(self, patient_client):
        DoctorFactory(
            user=UserFactory(role=Role.DOCTOR, is_active=False, last_name="Inactivo")
        )

        response = patient_client.get(LIST_URL)

        assert "Inactivo" not in response.content.decode()

    def test_paginates_and_keeps_the_filter(self, patient_client):
        cardiology = SpecialtyFactory(slug="cardiology")
        DoctorFactory.create_batch(
            DoctorListView.paginate_by + 1, specialties=[cardiology]
        )

        first = patient_client.get(LIST_URL, {"specialty": "cardiology"})
        second = patient_client.get(
            LIST_URL, {"specialty": "cardiology", "page": 2}, headers=HTMX
        )

        assert len(first.context["doctors"]) == DoctorListView.paginate_by
        assert "?specialty=cardiology&amp;page=2" in first.content.decode()
        assert len(second.context["doctors"]) == 1
        assert "?specialty=cardiology&amp;page=1" in second.content.decode()

    def test_query_count_does_not_grow_with_doctors(
        self, patient_client, django_assert_max_num_queries
    ):
        specialties = [SpecialtyFactory(slug="cardiology"), SpecialtyFactory()]
        DoctorFactory.create_batch(DoctorListView.paginate_by, specialties=specialties)

        # session + user, count, doctors + users, specialties, filter options
        with django_assert_max_num_queries(6):
            response = patient_client.get(LIST_URL)

        assert response.status_code == 200

    def test_english_page(self, patient_client):
        SpecialtyFactory(name="Cardiology", slug="cardiology")

        response = patient_client.get(LIST_URL, headers={"Accept-Language": "en"})
        html = response.content.decode()

        assert "Find a doctor" in html
        assert "Cardiology" in html


# ---------------------------------------------------------------------------
# Doctor detail and week of slots
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestDoctorDetail:
    def test_full_page_shows_doctor_and_specialties(self, patient_client, schedule):
        doctor = schedule.doctor
        doctor.specialties.add(SpecialtyFactory(name="Pediatrics", slug="pediatrics"))
        doctor.bio = "Atención de niños y adolescentes."
        doctor.save(update_fields=["bio", "updated_at"])

        response = patient_client.get(detail_url(doctor))
        html = response.content.decode()

        assert response.status_code == 200
        assertTemplateUsed(response, DETAIL_TEMPLATE)
        assertTemplateUsed(response, WEEK_PARTIAL)
        assert doctor.user.last_name in html
        assert "Pediatría" in html
        assert "Atención de niños y adolescentes." in html

    def test_unknown_doctor_is_404(self, patient_client):
        response = patient_client.get(f"/doctors/{uuid.uuid4()}/")

        assert response.status_code == 404

    def test_inactive_doctor_is_404(self, patient_client):
        doctor = DoctorFactory(user=UserFactory(role=Role.DOCTOR, is_active=False))

        response = patient_client.get(detail_url(doctor))

        assert response.status_code == 404

    def test_slots_are_shown_in_chilean_time(self, patient_client, schedule):
        start = tomorrow_at(9, 0)
        TimeSlotFactory(schedule=schedule, start_datetime=start)

        response = patient_client.get(detail_url(schedule.doctor))
        html = response.content.decode()

        utc_time = start.astimezone(datetime.UTC).strftime("%H:%M")
        assert "09:00" in html
        assert utc_time not in html

    def test_only_available_future_slots_are_shown(self, patient_client, schedule):
        TimeSlotFactory(schedule=schedule, start_datetime=tomorrow_at(9, 0))
        TimeSlotFactory(
            schedule=schedule,
            start_datetime=tomorrow_at(10, 0),
            status=TimeSlot.Status.RESERVED,
        )
        TimeSlotFactory(
            schedule=schedule,
            start_datetime=timezone.now() - datetime.timedelta(hours=2),
        )

        response = patient_client.get(detail_url(schedule.doctor))

        assert [
            slot for _, slots in response.context["week"].days for slot in slots
        ] == ([TimeSlot.objects.get(start_datetime=tomorrow_at(9, 0))])
        assert "10:00" not in response.content.decode()

    def test_each_slot_opens_the_booking_dialog(self, patient_client, schedule):
        """Paso 27: a link for browsers without JavaScript, hx-get for the rest."""
        slot = TimeSlotFactory(schedule=schedule, start_datetime=tomorrow_at(9, 0))

        html = patient_client.get(detail_url(schedule.doctor)).content.decode()

        assert f'href="/slots/{slot.pk}/book/"' in html
        assert f'hx-get="/slots/{slot.pk}/book/"' in html
        assert 'hx-target="#booking-dialog"' in html

    def test_page_has_the_booking_dialog_and_its_script(self, patient_client, schedule):
        html = patient_client.get(detail_url(schedule.doctor)).content.decode()

        assert '<dialog id="booking-dialog"' in html
        assert "web/js/booking-dialog.js" in html
        assert "Elige una hora para reservarla." in html

    def test_week_without_slots_shows_empty_state(self, patient_client, schedule):
        response = patient_client.get(detail_url(schedule.doctor))

        assert "No hay horas disponibles esta semana." in response.content.decode()

    def test_htmx_week_navigation_returns_only_the_week(self, patient_client, schedule):
        next_week = tomorrow_at(11, 0) + datetime.timedelta(days=7)
        TimeSlotFactory(schedule=schedule, start_datetime=next_week)

        response = patient_client.get(
            detail_url(schedule.doctor), {"week": 1}, headers=HTMX
        )
        html = response.content.decode()

        assertTemplateUsed(response, WEEK_PARTIAL)
        assertTemplateNotUsed(response, DETAIL_TEMPLATE)
        assert 'id="week-slots"' in html
        assert "11:00" in html
        assert "?week=0" in html
        assert "?week=2" in html

    def test_current_week_links_only_to_the_next_one(self, patient_client, schedule):
        response = patient_client.get(detail_url(schedule.doctor))
        html = response.content.decode()

        assert "?week=1" in html
        assert "?week=-1" not in html

    @pytest.mark.parametrize("raw", ["abc", "", "1.5"])
    def test_invalid_week_shows_the_current_week(self, patient_client, schedule, raw):
        response = patient_client.get(detail_url(schedule.doctor), {"week": raw})

        assert response.status_code == 200
        assert response.context["week"].index == 0

    def test_query_count_does_not_grow_with_slots(
        self, patient_client, schedule, django_assert_max_num_queries
    ):
        schedule.doctor.specialties.add(SpecialtyFactory(slug="cardiology"))
        for hour in range(9, 17):
            TimeSlotFactory(schedule=schedule, start_datetime=tomorrow_at(hour))

        # session + user, doctor + user, specialties, slots
        with django_assert_max_num_queries(5):
            response = patient_client.get(detail_url(schedule.doctor))

        assert response.status_code == 200

    def test_english_page(self, patient_client, schedule):
        response = patient_client.get(
            detail_url(schedule.doctor), headers={"Accept-Language": "en"}
        )

        assert "No available times this week." in response.content.decode()
