"""Integration tests for the API's time-zone behavior (ADR 0003).

TIME_ZONE is America/Santiago: datetimes are still stored in UTC, but they
are serialised with the Chilean offset and `__date` filters compare Chilean
calendar dates. January is summer in Chile (UTC-3).
"""

import datetime

import pytest
from rest_framework import status

from tests.factories import AppointmentFactory, PatientFactory, TimeSlotFactory

UTC = datetime.timezone.utc


@pytest.mark.django_db
class TestAppointmentTimeZone:
    def test_datetimes_are_serialized_with_chilean_offset(self, api_client):
        patient = PatientFactory()
        noon_utc = datetime.datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
        AppointmentFactory(
            patient=patient, slot=TimeSlotFactory(start_datetime=noon_utc)
        )
        api_client.force_authenticate(user=patient.user)

        response = api_client.get("/api/v1/appointments/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["slot_start"] == "2026-01-14T09:00:00-03:00"

    def test_date_filters_use_chilean_calendar_dates(self, api_client):
        """22:30 on 2026-01-14 in Chile is already 01:30 on 2026-01-15 in UTC."""
        patient = PatientFactory()
        late_evening_chile = datetime.datetime(2026, 1, 15, 1, 30, tzinfo=UTC)
        AppointmentFactory(
            patient=patient, slot=TimeSlotFactory(start_datetime=late_evening_chile)
        )
        api_client.force_authenticate(user=patient.user)

        same_day = api_client.get(
            "/api/v1/appointments/?date_from=2026-01-14&date_to=2026-01-14"
        )
        next_day = api_client.get(
            "/api/v1/appointments/?date_from=2026-01-15&date_to=2026-01-15"
        )

        assert same_day.data["count"] == 1
        assert next_day.data["count"] == 0
