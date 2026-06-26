"""Integration tests for django-filter FilterSets.

Covers:
- DoctorViewSet:     ?specialty=<slug>
- AppointmentViewSet: ?status=<status>, ?date_from=<date>, ?date_to=<date>
- ScheduleViewSet:   ?day_of_week=<int>, ?is_active=<bool>
"""

import datetime

import pytest
from django.utils import timezone
from rest_framework import status

from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestDoctorFilters:
    """GET /api/doctors/?specialty=<slug>"""

    def test_filter_by_specialty_returns_matching_doctors(self, api_client):
        cardiology = SpecialtyFactory(name="Cardiology", slug="cardiology")
        dermatology = SpecialtyFactory(name="Dermatology", slug="dermatology")
        doctor_cardio = DoctorFactory(specialties=[cardiology])
        DoctorFactory(specialties=[dermatology])

        api_client.force_authenticate(user=UserFactory())
        response = api_client.get("/api/v1/doctors/?specialty=cardiology")

        assert response.status_code == status.HTTP_200_OK
        ids = [d["id"] for d in response.data["results"]]
        assert str(doctor_cardio.id) in ids
        assert len(ids) == 1

    def test_filter_by_nonexistent_specialty_returns_empty(self, api_client):
        DoctorFactory()

        api_client.force_authenticate(user=UserFactory())
        response = api_client.get("/api/v1/doctors/?specialty=nonexistent")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_no_filter_returns_all_doctors(self, api_client):
        DoctorFactory()
        DoctorFactory()

        api_client.force_authenticate(user=UserFactory())
        response = api_client.get("/api/v1/doctors/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2


@pytest.mark.django_db
class TestAppointmentFilters:
    """GET /api/appointments/?status=<s>&date_from=<d>&date_to=<d>"""

    def test_filter_by_status_pending(self, api_client):
        patient = PatientFactory()
        AppointmentFactory(patient=patient, status="pending")
        AppointmentFactory(patient=patient, status="confirmed")

        api_client.force_authenticate(user=patient.user)
        response = api_client.get("/api/v1/appointments/?status=pending")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "pending"

    def test_filter_by_status_confirmed(self, api_client):
        patient = PatientFactory()
        AppointmentFactory(patient=patient, status="pending")
        AppointmentFactory(patient=patient, status="confirmed")
        AppointmentFactory(patient=patient, status="confirmed")

        api_client.force_authenticate(user=patient.user)
        response = api_client.get("/api/v1/appointments/?status=confirmed")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_filter_by_date_from(self, api_client):
        patient = PatientFactory()
        future = timezone.now() + datetime.timedelta(days=10)
        past = timezone.now() - datetime.timedelta(days=10)

        future_slot = TimeSlotFactory(start_datetime=future)
        past_slot = TimeSlotFactory(start_datetime=past)
        AppointmentFactory(patient=patient, slot=future_slot)
        AppointmentFactory(patient=patient, slot=past_slot)

        date_from = (timezone.now() + datetime.timedelta(days=5)).date().isoformat()
        api_client.force_authenticate(user=patient.user)
        response = api_client.get(f"/api/v1/appointments/?date_from={date_from}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_by_date_to(self, api_client):
        patient = PatientFactory()
        future = timezone.now() + datetime.timedelta(days=10)
        past = timezone.now() - datetime.timedelta(days=10)

        future_slot = TimeSlotFactory(start_datetime=future)
        past_slot = TimeSlotFactory(start_datetime=past)
        AppointmentFactory(patient=patient, slot=future_slot)
        AppointmentFactory(patient=patient, slot=past_slot)

        date_to = (timezone.now() - datetime.timedelta(days=5)).date().isoformat()
        api_client.force_authenticate(user=patient.user)
        response = api_client.get(f"/api/v1/appointments/?date_to={date_to}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_by_date_range(self, api_client):
        patient = PatientFactory()
        today = timezone.now()
        AppointmentFactory(
            patient=patient,
            slot=TimeSlotFactory(start_datetime=today + datetime.timedelta(days=2)),
        )
        AppointmentFactory(
            patient=patient,
            slot=TimeSlotFactory(start_datetime=today + datetime.timedelta(days=8)),
        )
        AppointmentFactory(
            patient=patient,
            slot=TimeSlotFactory(start_datetime=today - datetime.timedelta(days=2)),
        )

        date_from = (today + datetime.timedelta(days=1)).date().isoformat()
        date_to = (today + datetime.timedelta(days=5)).date().isoformat()

        api_client.force_authenticate(user=patient.user)
        response = api_client.get(
            f"/api/v1/appointments/?date_from={date_from}&date_to={date_to}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1


@pytest.mark.django_db
class TestScheduleFilters:
    """GET /api/schedules/?day_of_week=<int>&is_active=<bool>"""

    def test_filter_by_day_of_week(self, api_client):
        admin = UserFactory(role="admin")
        ScheduleFactory(day_of_week=0)  # Monday
        ScheduleFactory(day_of_week=1)  # Tuesday
        ScheduleFactory(day_of_week=1)  # Tuesday

        api_client.force_authenticate(user=admin)
        response = api_client.get("/api/v1/schedules/?day_of_week=1")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_filter_inactive_schedules(self, api_client):
        admin = UserFactory(role="admin")
        ScheduleFactory(is_active=True)
        ScheduleFactory(is_active=True)
        ScheduleFactory(is_active=False)

        api_client.force_authenticate(user=admin)
        response = api_client.get("/api/v1/schedules/?is_active=false")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_active_schedules(self, api_client):
        admin = UserFactory(role="admin")
        ScheduleFactory(is_active=True)
        ScheduleFactory(is_active=False)

        api_client.force_authenticate(user=admin)
        response = api_client.get("/api/v1/schedules/?is_active=true")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
