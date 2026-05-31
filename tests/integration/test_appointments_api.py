"""Integration tests for the appointments API.

Tests the full HTTP stack: URL → ViewSet → Serializer → Service → DB.
Uses APIClient with force_authenticate — no JWT overhead needed here.

Coverage targets:
  apps/appointments/views.py      ≥ 80%
  apps/appointments/serializers.py ≥ 80%
  apps/appointments/services.py   ≥ 90%
  apps/core/permissions.py        = 100%
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.appointments.models import Appointment, TimeSlot
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    ScheduleFactory,
    TimeSlotFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patient_user(db):
    return UserFactory(role=Role.PATIENT)


@pytest.fixture
def doctor_user(db):
    return UserFactory(role=Role.DOCTOR)


@pytest.fixture
def admin_user(db):
    return UserFactory(role=Role.ADMIN, is_staff=True)


@pytest.fixture
def patient(db, patient_user):
    return PatientFactory(user=patient_user)


@pytest.fixture
def doctor(db, doctor_user):
    return DoctorFactory(user=doctor_user)


@pytest.fixture
def available_slot(db, doctor):
    """A future available slot linked to the test doctor."""
    schedule = ScheduleFactory(doctor=doctor)
    # Use a slot from the signal-generated ones, or create directly
    slot = TimeSlot.objects.filter(
        schedule=schedule, status=TimeSlot.Status.AVAILABLE
    ).first()
    if not slot:
        slot = TimeSlotFactory(schedule=schedule, status=TimeSlot.Status.AVAILABLE)
    return slot


@pytest.fixture
def auth_client_patient(patient_user, patient):
    client = APIClient()
    client.force_authenticate(user=patient_user)
    return client


@pytest.fixture
def auth_client_doctor(doctor_user, doctor):
    client = APIClient()
    client.force_authenticate(user=doctor_user)
    return client


@pytest.fixture
def auth_client_admin(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


# ---------------------------------------------------------------------------
# TestAppointmentCreate
# ---------------------------------------------------------------------------


class TestAppointmentCreate:
    """POST /api/appointments/ — booking a new appointment."""

    url = "/api/appointments/"

    def test_patient_can_book_available_slot(
        self, auth_client_patient, available_slot, patient
    ):
        """Happy path: patient books an available slot → 201."""
        response = auth_client_patient.post(
            self.url,
            {"slot": str(available_slot.id), "reason": "Annual checkup"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Appointment.objects.filter(patient=patient).exists()

    def test_booking_reserves_the_slot(
        self, auth_client_patient, available_slot, patient
    ):
        """Creating an appointment marks the slot as RESERVED."""
        auth_client_patient.post(
            self.url,
            {"slot": str(available_slot.id)},
            format="json",
        )
        available_slot.refresh_from_db()
        assert available_slot.status == TimeSlot.Status.RESERVED

    def test_unauthenticated_request_returns_401(self, db, available_slot):
        """Anonymous requests are rejected with 401."""
        client = APIClient()
        response = client.post(
            self.url,
            {"slot": str(available_slot.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_cannot_book_appointment(self, auth_client_doctor, available_slot):
        """Doctor role cannot create appointments — 403."""
        response = auth_client_doctor.post(
            self.url,
            {"slot": str(available_slot.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reserved_slot_returns_400(self, auth_client_patient, available_slot):
        """Trying to book a reserved slot → 400."""
        available_slot.status = TimeSlot.Status.RESERVED
        available_slot.save(update_fields=["status", "updated_at"])

        response = auth_client_patient.post(
            self.url,
            {"slot": str(available_slot.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_overlapping_appointment_returns_400(
        self, auth_client_patient, patient, available_slot
    ):
        """Patient with existing appointment at same time → 400."""
        # Create a pending appointment at the same time
        AppointmentFactory(
            patient=patient,
            status=Appointment.Status.PENDING,
            slot=available_slot,
        )
        # The signal already created slots for any new schedule at the same times.
        # Use a different schedule and find the slot the signal already created
        # at the same datetime — avoids UniqueViolation on (schedule, start_datetime).
        other_schedule = ScheduleFactory()
        overlapping = TimeSlot.objects.filter(
            schedule=other_schedule,
            start_datetime=available_slot.start_datetime,
            status=TimeSlot.Status.AVAILABLE,
        ).first()
        if overlapping is None:
            # Fallback: signal didn't generate for this date (e.g. not a Monday)
            pytest.skip("No overlapping slot available for this weekday")
        response = auth_client_patient.post(
            self.url,
            {"slot": str(overlapping.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# TestAppointmentList
# ---------------------------------------------------------------------------


class TestAppointmentList:
    """GET /api/appointments/ — listing appointments."""

    url = "/api/appointments/"

    def test_patient_sees_only_own_appointments(
        self, db, auth_client_patient, patient, doctor
    ):
        """Patient only sees their own appointments — not others'."""
        own = AppointmentFactory(patient=patient, doctor=doctor)
        other_patient = PatientFactory()
        AppointmentFactory(patient=other_patient, doctor=doctor)

        response = auth_client_patient.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        # Response is paginated: {"count": N, "results": [...]}
        results = response.data["results"]
        ids = [item["id"] for item in results]
        assert str(own.id) in ids
        assert len(ids) == 1

    def test_doctor_sees_only_own_appointments(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Doctor only sees appointments assigned to them."""
        own = AppointmentFactory(patient=patient, doctor=doctor)
        other_doctor = DoctorFactory()
        AppointmentFactory(patient=patient, doctor=other_doctor)

        response = auth_client_doctor.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        ids = [item["id"] for item in results]
        assert str(own.id) in ids
        assert len(ids) == 1

    def test_admin_sees_all_appointments(self, db, auth_client_admin, patient, doctor):
        """Admin sees all appointments across all users."""
        AppointmentFactory(patient=patient, doctor=doctor)
        AppointmentFactory(patient=patient, doctor=doctor)

        response = auth_client_admin.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_unauthenticated_returns_401(self, db):
        """Anonymous requests are rejected."""
        client = APIClient()
        response = client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# TestAppointmentActions (state transitions)
# ---------------------------------------------------------------------------


class TestAppointmentActions:
    """POST /api/appointments/{id}/confirm|cancel|complete|no-show/"""

    def test_doctor_can_confirm_own_appointment(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Doctor confirms a pending appointment → 200, status=confirmed."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        response = auth_client_doctor.post(f"/api/appointments/{appt.id}/confirm/")
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CONFIRMED

    def test_patient_cannot_confirm_appointment(
        self, db, auth_client_patient, patient, doctor
    ):
        """Patient cannot confirm — 403."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        response = auth_client_patient.post(f"/api/appointments/{appt.id}/confirm/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patient_can_cancel_own_appointment(
        self, db, auth_client_patient, patient, doctor
    ):
        """Patient cancels their own pending appointment → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        response = auth_client_patient.post(f"/api/appointments/{appt.id}/cancel/")
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED

    def test_cancel_frees_slot(self, db, auth_client_patient, patient, doctor):
        """Cancelling an appointment returns the slot to AVAILABLE."""
        slot = TimeSlotFactory(status=TimeSlot.Status.RESERVED)
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            slot=slot,
            status=Appointment.Status.PENDING,
        )
        auth_client_patient.post(f"/api/appointments/{appt.id}/cancel/")
        slot.refresh_from_db()
        assert slot.status == TimeSlot.Status.AVAILABLE

    def test_doctor_can_complete_confirmed_appointment(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Doctor completes a confirmed appointment → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
        )
        response = auth_client_doctor.post(f"/api/appointments/{appt.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.COMPLETED

    def test_complete_pending_returns_400(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Completing a pending appointment → 400 (invalid transition)."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        response = auth_client_doctor.post(f"/api/appointments/{appt.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_doctor_can_mark_no_show(self, db, auth_client_doctor, patient, doctor):
        """Doctor marks confirmed appointment as no-show → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
        )
        response = auth_client_doctor.post(f"/api/appointments/{appt.id}/no-show/")
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.NO_SHOW

    def test_other_doctor_cannot_confirm_appointment(
        self, db, doctor_user, patient, doctor
    ):
        """A different doctor cannot confirm another doctor's appointment.

        Returns 404 (not 403) — the queryset filters by doctor__user so the
        appointment is invisible to other doctors. This prevents object
        enumeration: a 403 would reveal the object exists.
        """
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        other_doctor = DoctorFactory()
        client = APIClient()
        client.force_authenticate(user=other_doctor.user)

        response = client.post(f"/api/appointments/{appt.id}/confirm/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# TestDoctorAvailableSlots
# ---------------------------------------------------------------------------


class TestDoctorAvailableSlots:
    """GET /api/doctors/{id}/available-slots/"""

    def test_returns_available_slots_for_doctor(self, db, auth_client_patient, doctor):
        """Authenticated user can list available slots for a doctor."""
        schedule = ScheduleFactory(doctor=doctor)
        # Slots auto-generated by signal — filter available ones
        slots_count = TimeSlot.objects.filter(
            schedule=schedule, status=TimeSlot.Status.AVAILABLE
        ).count()

        response = auth_client_patient.get(f"/api/doctors/{doctor.id}/available-slots/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == slots_count

    def test_reserved_slots_are_excluded(self, db, auth_client_patient, doctor):
        """Reserved slots do not appear in available-slots response."""
        schedule = ScheduleFactory(doctor=doctor)
        slot = TimeSlot.objects.filter(
            schedule=schedule, status=TimeSlot.Status.AVAILABLE
        ).first()
        if slot:
            slot.status = TimeSlot.Status.RESERVED
            slot.save(update_fields=["status", "updated_at"])

        response = auth_client_patient.get(f"/api/doctors/{doctor.id}/available-slots/")
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["status"] == TimeSlot.Status.AVAILABLE

    def test_unauthenticated_returns_401(self, db, doctor):
        """Anonymous requests to available-slots → 401."""
        client = APIClient()
        response = client.get(f"/api/doctors/{doctor.id}/available-slots/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# TestDoctorList
# ---------------------------------------------------------------------------


class TestDoctorList:
    """GET /api/doctors/ — listing doctors."""

    url = "/api/doctors/"

    def test_authenticated_user_can_list_doctors(self, db, auth_client_patient, doctor):
        """Any authenticated user can list doctors."""
        response = auth_client_patient.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 1

    def test_list_returns_expected_fields(self, db, auth_client_patient, doctor):
        """List response contains full_name, consultation_duration, specialties_count."""
        response = auth_client_patient.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        # Response is paginated: {"count": N, "results": [...]}
        first = response.data["results"][0]
        assert "full_name" in first
        assert "consultation_duration" in first
        assert "specialties_count" in first
