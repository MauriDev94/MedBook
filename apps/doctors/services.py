"""Business logic for the doctors app."""

import datetime

from django.utils import timezone

from apps.appointments.models import TimeSlot


def get_available_slots(doctor, days_ahead: int = 7):
    """Return available TimeSlots for a doctor over the next N days.

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
            start_datetime__date__gte=today,
            start_datetime__date__lte=end_date,
        )
        .select_related("schedule__doctor")
        .order_by("start_datetime")
    )
