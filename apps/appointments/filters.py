"""FilterSets for the appointments app."""

import django_filters

from apps.appointments.models import Appointment


class AppointmentFilter(django_filters.FilterSet):
    """Filter appointments by status and slot date range.

    Usage: GET /api/appointments/?status=pending&date_from=2025-01-01&date_to=2025-12-31
    """

    date_from = django_filters.DateFilter(
        field_name="slot__start_datetime",
        lookup_expr="date__gte",
        label="Slot date from (inclusive)",
    )
    date_to = django_filters.DateFilter(
        field_name="slot__start_datetime",
        lookup_expr="date__lte",
        label="Slot date to (inclusive)",
    )

    class Meta:
        model = Appointment
        fields = ["status", "date_from", "date_to"]
