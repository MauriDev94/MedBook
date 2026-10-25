"""Tests for the doctor catalog in apps/doctors/services.py (Paso 26).

list_doctors() and list_specialties() feed the web catalog.
get_available_slots_week() returns one week of bookable slots (available and
not started yet) grouped by their Chilean date (ADR 0003).
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.appointments.models import TimeSlot
from apps.doctors import services
from tests.factories import (
    DoctorFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)

CHILE = ZoneInfo("America/Santiago")
# Friday 23 October 2026, 15:00 in Chile (UTC-3, summer time)
NOW = datetime.datetime(2026, 10, 23, 15, 0, tzinfo=CHILE)
TODAY = NOW.date()


def days_after_today(days: int) -> datetime.date:
    return TODAY + datetime.timedelta(days=days)


@pytest.fixture
def frozen_now(monkeypatch):
    """Pin timezone.now() (and so timezone.localdate()) to NOW."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def schedule(db, frozen_now):
    """A schedule without the slots its post_save signal generated."""
    schedule = ScheduleFactory()
    TimeSlot.objects.filter(schedule=schedule).delete()
    return schedule


def slot_at(schedule, day, hour, minute=0, **kwargs):
    """A TimeSlot starting at day + hour:minute, Chilean time."""
    start = datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=CHILE)
    return TimeSlotFactory(schedule=schedule, start_datetime=start, **kwargs)


# ---------------------------------------------------------------------------
# list_doctors / list_specialties
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestListDoctors:
    def test_orders_by_last_name(self):
        soto = DoctorFactory(user__last_name="Soto")
        araya = DoctorFactory(user__last_name="Araya")

        assert list(services.list_doctors()) == [araya, soto]

    def test_filters_by_specialty_slug(self):
        cardiology = SpecialtyFactory(slug="cardiology")
        cardiologist = DoctorFactory(specialties=[cardiology])
        DoctorFactory(specialties=[SpecialtyFactory(slug="dermatology")])

        assert list(services.list_doctors(specialty_slug="cardiology")) == [
            cardiologist
        ]

    @pytest.mark.parametrize("slug", [None, ""])
    def test_no_slug_lists_every_doctor(self, slug):
        DoctorFactory.create_batch(2)

        assert services.list_doctors(specialty_slug=slug).count() == 2

    def test_unknown_slug_lists_nobody(self):
        DoctorFactory()

        assert not services.list_doctors(specialty_slug="no-such-specialty").exists()

    def test_skips_doctors_whose_account_is_inactive(self):
        active = DoctorFactory()
        DoctorFactory(user=UserFactory(role="doctor", is_active=False))

        assert list(services.list_doctors()) == [active]

    def test_loads_users_and_specialties_in_two_queries(
        self, django_assert_num_queries
    ):
        specialties = [SpecialtyFactory(slug="cardiology"), SpecialtyFactory()]
        DoctorFactory.create_batch(3, specialties=specialties)

        with django_assert_num_queries(2):
            for doctor in services.list_doctors():
                assert doctor.user.email
                assert len(doctor.specialties.all()) == 2


@pytest.mark.django_db
class TestListSpecialties:
    def test_orders_by_name(self):
        SpecialtyFactory(name="Pediatrics", slug="pediatrics")
        SpecialtyFactory(name="Cardiology", slug="cardiology")

        names = [specialty.name for specialty in services.list_specialties()]

        assert names == sorted(names)
        assert {"Cardiology", "Pediatrics"} <= set(names)


# ---------------------------------------------------------------------------
# get_available_slots (API available-slots)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestGetAvailableSlots:
    def test_skips_slots_that_already_started(self, schedule):
        """Paso 30: filtering by date alone kept today's started slots."""
        slot_at(schedule, TODAY, 14, 30)
        later_today = slot_at(schedule, TODAY, 15, 30)

        assert list(services.get_available_slots(schedule.doctor)) == [later_today]


# ---------------------------------------------------------------------------
# week_of
# ---------------------------------------------------------------------------
class TestWeekOf:
    """The booking week that holds a date (Paso 27: back to the slot's week)."""

    @pytest.mark.parametrize(
        ("days", "expected"),
        [
            pytest.param(0, 0, id="today"),
            pytest.param(6, 0, id="last-day-of-current-week"),
            pytest.param(7, 1, id="first-day-of-next-week"),
            pytest.param(20, 2, id="third-week"),
            pytest.param(60, services.BOOKING_WEEKS_AHEAD - 1, id="past-horizon"),
            pytest.param(-3, 0, id="past-date"),
        ],
    )
    def test_counts_weeks_from_today(self, frozen_now, days, expected):
        assert services.week_of(days_after_today(days)) == expected


# ---------------------------------------------------------------------------
# get_available_slots_week
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestGetAvailableSlotsWeek:
    def test_groups_slots_by_chilean_date(self, schedule):
        first = slot_at(schedule, days_after_today(1), 10)
        second = slot_at(schedule, days_after_today(1), 11)
        monday = slot_at(schedule, days_after_today(3), 9)

        week = services.get_available_slots_week(schedule.doctor)

        assert week.days == [
            (days_after_today(1), [first, second]),
            (days_after_today(3), [monday]),
        ]

    def test_late_evening_slot_keeps_its_chilean_date(self, schedule):
        """22:30 in Chile is 01:30 UTC of the next day."""
        late = slot_at(schedule, days_after_today(1), 22, 30)

        week = services.get_available_slots_week(schedule.doctor)

        assert late.start_datetime.astimezone(datetime.UTC).date() == (
            days_after_today(2)
        )
        assert week.days == [(days_after_today(1), [late])]

    def test_skips_slots_that_already_started(self, schedule):
        slot_at(schedule, TODAY, 14, 30)
        later_today = slot_at(schedule, TODAY, 15, 30)

        week = services.get_available_slots_week(schedule.doctor)

        assert week.days == [(TODAY, [later_today])]

    @pytest.mark.parametrize(
        "status", [TimeSlot.Status.RESERVED, TimeSlot.Status.BLOCKED]
    )
    def test_skips_slots_that_are_not_available(self, schedule, status):
        slot_at(schedule, days_after_today(1), 10, status=status)

        week = services.get_available_slots_week(schedule.doctor)

        assert week.days == []

    def test_skips_other_doctors_slots(self, schedule):
        other_schedule = ScheduleFactory()
        TimeSlot.objects.filter(schedule=other_schedule).delete()
        slot_at(other_schedule, days_after_today(1), 10)

        week = services.get_available_slots_week(schedule.doctor)

        assert week.days == []

    def test_current_week_is_today_and_the_next_six_days(self, schedule):
        sixth_day = slot_at(schedule, days_after_today(6), 10)
        slot_at(schedule, days_after_today(7), 10)

        week = services.get_available_slots_week(schedule.doctor)

        assert week.start == TODAY
        assert week.end == days_after_today(6)
        assert week.days == [(days_after_today(6), [sixth_day])]

    def test_next_week_starts_seven_days_after_today(self, schedule):
        slot_at(schedule, days_after_today(6), 10)
        seventh_day = slot_at(schedule, days_after_today(7), 10)

        week = services.get_available_slots_week(schedule.doctor, week=1)

        assert week.start == days_after_today(7)
        assert week.days == [(days_after_today(7), [seventh_day])]

    @pytest.mark.parametrize(
        ("requested", "expected"),
        [
            pytest.param(-3, 0, id="before-current-week"),
            pytest.param(99, services.BOOKING_WEEKS_AHEAD - 1, id="past-horizon"),
        ],
    )
    def test_week_is_clamped_to_the_booking_horizon(
        self, schedule, requested, expected
    ):
        week = services.get_available_slots_week(schedule.doctor, week=requested)

        assert week.index == expected
        assert week.start == days_after_today(7 * expected)

    def test_current_week_has_only_a_next_week(self, schedule):
        week = services.get_available_slots_week(schedule.doctor)

        assert not week.has_previous
        assert week.has_next
        assert week.next_index == 1

    def test_last_week_has_only_a_previous_week(self, schedule):
        last = services.BOOKING_WEEKS_AHEAD - 1

        week = services.get_available_slots_week(schedule.doctor, week=last)

        assert week.has_previous
        assert not week.has_next
        assert week.previous_index == last - 1

    def test_runs_a_single_query(self, schedule, django_assert_num_queries):
        for hour in (9, 10, 11):
            slot_at(schedule, days_after_today(1), hour)

        with django_assert_num_queries(1):
            services.get_available_slots_week(schedule.doctor)
