"""Integration tests for ScheduleViewSet.

Covers:
- GET  /api/schedules/          → list (doctor = own; admin = all; patient = empty)
- POST /api/schedules/          → create (doctor only; doctor auto-assigned)
- GET  /api/schedules/{id}/     → retrieve
- PATCH /api/schedules/{id}/    → partial update
- DELETE /api/schedules/{id}/   → soft delete (is_active=False)
"""

import datetime

import pytest
from rest_framework import status

from apps.doctors.models import Schedule
from tests.factories import DoctorFactory, PatientFactory, ScheduleFactory, UserFactory


@pytest.mark.django_db
class TestScheduleList:
    """GET /api/schedules/ — list schedules."""

    def test_doctor_sees_only_own_schedules(self, api_client):
        doctor_a = DoctorFactory()
        doctor_b = DoctorFactory()
        ScheduleFactory(doctor=doctor_a)
        ScheduleFactory(doctor=doctor_b)

        api_client.force_authenticate(user=doctor_a.user)
        response = api_client.get("/api/v1/schedules/")

        assert response.status_code == status.HTTP_200_OK
        ids = [s["id"] for s in response.data["results"]]
        assert all(Schedule.objects.get(id=sid).doctor == doctor_a for sid in ids)
        assert len(ids) == 1

    def test_admin_sees_all_schedules(self, api_client):
        admin = UserFactory(role="admin")
        ScheduleFactory()
        ScheduleFactory()

        api_client.force_authenticate(user=admin)
        response = api_client.get("/api/v1/schedules/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_patient_sees_empty_list(self, api_client):
        patient = PatientFactory()
        ScheduleFactory()

        api_client.force_authenticate(user=patient.user)
        response = api_client.get("/api/v1/schedules/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/schedules/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_has_expected_fields(self, api_client):
        doctor = DoctorFactory()
        ScheduleFactory(doctor=doctor)

        api_client.force_authenticate(user=doctor.user)
        response = api_client.get("/api/v1/schedules/")

        assert response.status_code == status.HTTP_200_OK
        schedule = response.data["results"][0]
        for field in [
            "id",
            "day_of_week",
            "day_of_week_display",
            "start_time",
            "end_time",
            "is_active",
        ]:
            assert field in schedule, f"Missing field: {field}"


@pytest.mark.django_db
class TestScheduleCreate:
    """POST /api/schedules/ — create schedule (doctor only)."""

    def test_doctor_creates_schedule(self, api_client):
        doctor = DoctorFactory()
        api_client.force_authenticate(user=doctor.user)

        response = api_client.post(
            "/api/v1/schedules/",
            {"day_of_week": 1, "start_time": "09:00", "end_time": "17:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Schedule.objects.filter(doctor=doctor, day_of_week=1).exists()

    def test_doctor_auto_assigned_from_request_user(self, api_client):
        doctor = DoctorFactory()
        other_doctor = DoctorFactory()
        api_client.force_authenticate(user=doctor.user)

        response = api_client.post(
            "/api/v1/schedules/",
            {
                "day_of_week": 2,
                "start_time": "08:00",
                "end_time": "14:00",
                "doctor": str(other_doctor.id),  # should be ignored
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        schedule = Schedule.objects.get(id=response.data["id"])
        assert schedule.doctor == doctor

    def test_patient_cannot_create_schedule(self, api_client):
        patient = PatientFactory()
        api_client.force_authenticate(user=patient.user)

        response = api_client.post(
            "/api/v1/schedules/",
            {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_time_range_returns_400(self, api_client):
        doctor = DoctorFactory()
        api_client.force_authenticate(user=doctor.user)

        response = api_client.post(
            "/api/v1/schedules/",
            {"day_of_week": 0, "start_time": "17:00", "end_time": "09:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_equal_times_returns_400(self, api_client):
        doctor = DoctorFactory()
        api_client.force_authenticate(user=doctor.user)

        response = api_client.post(
            "/api/v1/schedules/",
            {"day_of_week": 0, "start_time": "09:00", "end_time": "09:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            "/api/v1/schedules/",
            {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestScheduleRetrieve:
    """GET /api/schedules/{id}/ — retrieve single schedule."""

    def test_doctor_retrieves_own_schedule(self, api_client):
        doctor = DoctorFactory()
        schedule = ScheduleFactory(doctor=doctor)

        api_client.force_authenticate(user=doctor.user)
        response = api_client.get(f"/api/v1/schedules/{schedule.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["id"]) == str(schedule.id)

    def test_doctor_cannot_retrieve_other_doctors_schedule(self, api_client):
        doctor_a = DoctorFactory()
        doctor_b = DoctorFactory()
        schedule_b = ScheduleFactory(doctor=doctor_b)

        api_client.force_authenticate(user=doctor_a.user)
        response = api_client.get(f"/api/v1/schedules/{schedule_b.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_retrieves_any_schedule(self, api_client):
        admin = UserFactory(role="admin")
        schedule = ScheduleFactory()

        api_client.force_authenticate(user=admin)
        response = api_client.get(f"/api/v1/schedules/{schedule.id}/")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestScheduleUpdate:
    """PATCH /api/schedules/{id}/ — partial update."""

    def test_doctor_updates_own_schedule(self, api_client):
        doctor = DoctorFactory()
        schedule = ScheduleFactory(doctor=doctor, start_time=datetime.time(9, 0))

        api_client.force_authenticate(user=doctor.user)
        response = api_client.patch(
            f"/api/v1/schedules/{schedule.id}/",
            {"start_time": "10:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        schedule.refresh_from_db()
        assert schedule.start_time == datetime.time(10, 0)

    def test_doctor_cannot_update_other_doctors_schedule(self, api_client):
        doctor_a = DoctorFactory()
        doctor_b = DoctorFactory()
        schedule_b = ScheduleFactory(doctor=doctor_b)

        api_client.force_authenticate(user=doctor_a.user)
        response = api_client.patch(
            f"/api/v1/schedules/{schedule_b.id}/",
            {"start_time": "10:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_updates_any_schedule(self, api_client):
        admin = UserFactory(role="admin")
        schedule = ScheduleFactory()

        api_client.force_authenticate(user=admin)
        response = api_client.patch(
            f"/api/v1/schedules/{schedule.id}/",
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestScheduleDelete:
    """DELETE /api/schedules/{id}/ — soft delete."""

    def test_delete_soft_deletes_schedule(self, api_client):
        doctor = DoctorFactory()
        schedule = ScheduleFactory(doctor=doctor)

        api_client.force_authenticate(user=doctor.user)
        response = api_client.delete(f"/api/v1/schedules/{schedule.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        schedule.refresh_from_db()
        assert schedule.is_active is False

    def test_delete_does_not_remove_from_db(self, api_client):
        doctor = DoctorFactory()
        schedule = ScheduleFactory(doctor=doctor)
        schedule_id = schedule.id

        api_client.force_authenticate(user=doctor.user)
        api_client.delete(f"/api/v1/schedules/{schedule.id}/")

        assert Schedule.objects.filter(id=schedule_id).exists()

    def test_doctor_cannot_delete_other_doctors_schedule(self, api_client):
        doctor_a = DoctorFactory()
        doctor_b = DoctorFactory()
        schedule_b = ScheduleFactory(doctor=doctor_b)

        api_client.force_authenticate(user=doctor_a.user)
        response = api_client.delete(f"/api/v1/schedules/{schedule_b.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_delete_any_schedule(self, api_client):
        admin = UserFactory(role="admin")
        schedule = ScheduleFactory()

        api_client.force_authenticate(user=admin)
        response = api_client.delete(f"/api/v1/schedules/{schedule.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        schedule.refresh_from_db()
        assert schedule.is_active is False

    def test_patient_cannot_delete_schedule(self, api_client):
        patient = PatientFactory()
        schedule = ScheduleFactory()

        api_client.force_authenticate(user=patient.user)
        response = api_client.delete(f"/api/v1/schedules/{schedule.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
