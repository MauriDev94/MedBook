"""Shared utility functions for the MedBook project."""

from django.utils import formats, timezone


def get_display_name(user) -> str:
    """Return user's full name, or email as fallback.

    Used across models and serializers wherever a human-readable name
    is needed. Centralizes the pattern: obj.full_name or obj.email.
    """
    return user.full_name or user.email


def moment_of(slot) -> dict:
    """Weekday, date and time of a slot in Chilean time, for messages.

    Formatted in the active language: the web uses the visitor's, and the
    emails the clinic's (apps.notifications.services).
    """
    start = timezone.localtime(slot.start_datetime)
    return {
        "weekday": formats.date_format(start, "l"),
        "date": formats.date_format(start, "MONTH_DAY_FORMAT"),
        "time": formats.time_format(start, "H:i"),
    }
