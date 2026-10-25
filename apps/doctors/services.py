"""Business logic for the doctors app."""

import datetime
from dataclasses import dataclass

from django.utils import timezone

from apps.appointments.models import TimeSlot
from apps.doctors.models import Doctor, Specialty

# Weeks of availability a patient can browse on the web, counting the current one
BOOKING_WEEKS_AHEAD = 4


def get_available_slots(doctor, days_ahead: int = 7):
    """Return available TimeSlots for a doctor over the next N days.

    Slots that already started are left out, even when they are today's.

    Args:
        doctor: Doctor instance.
        days_ahead: Number of days ahead to look (clamped to 1–365).

    Returns:
        QuerySet of available TimeSlot objects ordered by start_datetime.
    """
    days_ahead = min(max(days_ahead, 1), 365)
    today = timezone.localdate()
    end_date = today + datetime.timedelta(days=days_ahead)

    return (
        TimeSlot.objects.filter(
            schedule__doctor=doctor,
            status=TimeSlot.Status.AVAILABLE,
            start_datetime__gt=timezone.now(),
            start_datetime__date__gte=today,
            start_datetime__date__lte=end_date,
        )
        .select_related("schedule__doctor")
        .order_by("start_datetime")
    )


def list_doctors(specialty_slug: str | None = None):
    """Return the doctors whose account is active, ordered by last name.

    Users and specialties are loaded up front, so listing them causes no
    N+1. An empty or missing slug means no specialty filter.
    """
    doctors = (
        Doctor.objects.filter(user__is_active=True)
        .select_related("user")
        .prefetch_related("specialties")
        .order_by("user__last_name", "user__first_name", "pk")
    )
    if specialty_slug:
        doctors = doctors.filter(specialties__slug=specialty_slug)
    return doctors


def list_specialties():
    """Return every specialty ordered by name."""
    return Specialty.objects.order_by("name")


@dataclass(frozen=True)
class SlotWeek:
    """Seven days of a doctor's available slots, grouped by Chilean date.

    `index` 0 is the week that starts today. `days` holds only the dates
    that have slots, as (date, slots) pairs in chronological order.
    """

    index: int
    start: datetime.date
    days: list[tuple[datetime.date, list[TimeSlot]]]

    @property
    def end(self) -> datetime.date:
        """The last day of the week (inclusive)."""
        return self.start + datetime.timedelta(days=6)

    @property
    def has_previous(self) -> bool:
        return self.index > 0

    @property
    def has_next(self) -> bool:
        return self.index < BOOKING_WEEKS_AHEAD - 1

    @property
    def previous_index(self) -> int:
        return self.index - 1

    @property
    def next_index(self) -> int:
        return self.index + 1


def get_available_slots_week(doctor, week: int = 0) -> SlotWeek:
    """Return one week of a doctor's bookable slots.

    Week 0 is today plus the next six days, week 1 the seven days after
    that, and so on; `week` is clamped to 0..BOOKING_WEEKS_AHEAD - 1. Only
    available slots that have not started yet are included. The `__date`
    lookups compare Chilean dates (TIME_ZONE, ADR 0003).
    """
    week = min(max(week, 0), BOOKING_WEEKS_AHEAD - 1)
    start = timezone.localdate() + datetime.timedelta(weeks=week)
    slots = TimeSlot.objects.filter(
        schedule__doctor=doctor,
        status=TimeSlot.Status.AVAILABLE,
        start_datetime__gt=timezone.now(),
        start_datetime__date__gte=start,
        start_datetime__date__lt=start + datetime.timedelta(days=7),
    ).order_by("start_datetime")

    days: dict[datetime.date, list[TimeSlot]] = {}
    for slot in slots:
        days.setdefault(timezone.localdate(slot.start_datetime), []).append(slot)
    return SlotWeek(index=week, start=start, days=list(days.items()))
