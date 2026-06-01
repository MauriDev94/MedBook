"""FilterSets for the doctors app."""

import django_filters

from apps.doctors.models import Doctor, Schedule


class DoctorFilter(django_filters.FilterSet):
    """Filter doctors by specialty slug.

    Usage: GET /api/doctors/?specialty=cardiology
    """

    specialty = django_filters.CharFilter(
        field_name="specialties__slug",
        lookup_expr="exact",
        label="Specialty slug",
    )

    class Meta:
        model = Doctor
        fields = ["specialty"]


class ScheduleFilter(django_filters.FilterSet):
    """Filter schedules by day of week and active status.

    Usage: GET /api/schedules/?day_of_week=1&is_active=true
    """

    class Meta:
        model = Schedule
        fields = ["day_of_week", "is_active"]
