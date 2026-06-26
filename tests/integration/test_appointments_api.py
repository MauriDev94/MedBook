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

    url = "/api/v1/appointments/"

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
        """Patient with existing appointment at same time → 400.

        Creates a second slot at the SAME datetime on a DIFFERENT schedule to
        avoid UniqueViolation on (schedule, start_datetime). The overlap check
        is on datetime range, not on schedule.
        """
        # Create a pending appointment occupying available_slot
        AppointmentFactory(
            patient=patient,
            status=Appointment.Status.PENDING,
            slot=available_slot,
        )
        # Build a second slot at the same datetime on a fresh schedule
        other_schedule = ScheduleFactory()
        # Use any signal-generated slot that matches the datetime, or create directly
        overlapping = TimeSlot.objects.filter(
            schedule=other_schedule,
            start_datetime=available_slot.start_datetime,
            status=TimeSlot.Status.AVAILABLE,
        ).first()
        if overlapping is None:
            # Signal didn't generate for this weekday — create directly
            overlapping = TimeSlotFactory(
                schedule=other_schedule,
                start_datetime=available_slot.start_datetime,
                end_datetime=available_slot.end_datetime,
                status=TimeSlot.Status.AVAILABLE,
            )
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

    url = "/api/v1/appointments/"

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
        response = auth_client_doctor.post(f"/api/v1/appointments/{appt.id}/confirm/")
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
        response = auth_client_patient.post(f"/api/v1/appointments/{appt.id}/confirm/")
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
        response = auth_client_patient.post(f"/api/v1/appointments/{appt.id}/cancel/")
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
        auth_client_patient.post(f"/api/v1/appointments/{appt.id}/cancel/")
        slot.refresh_from_db()
        assert slot.status == TimeSlot.Status.AVAILABLE

    def test_cancel_enforces_object_ownership_not_just_queryset(
        self, db, auth_client_admin, patient, doctor
    ):
        """Ownership on cancel is enforced at the object level, not only via queryset.

        Admin's get_queryset returns ALL appointments, so get_object() succeeds.
        But admin is neither the patient nor the doctor of the appointment, so the
        object-level permission (IsPatientOfAppointment | IsDoctorOfAppointment)
        must deny → 403. This proves the permission does work the queryset can't.
        """
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.PENDING,
        )
        response = auth_client_admin.post(f"/api/v1/appointments/{appt.id}/cancel/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.PENDING  # unchanged

    def test_doctor_can_cancel_own_appointment(
        self, db, auth_client_doctor, patient, doctor
    ):
        """The assigned doctor can also cancel the appointment → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
        )
        response = auth_client_doctor.post(f"/api/v1/appointments/{appt.id}/cancel/")
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED

    def test_doctor_can_complete_confirmed_appointment(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Doctor completes a confirmed appointment → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
        )
        response = auth_client_doctor.post(f"/api/v1/appointments/{appt.id}/complete/")
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
        response = auth_client_doctor.post(f"/api/v1/appointments/{appt.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_doctor_can_mark_no_show(self, db, auth_client_doctor, patient, doctor):
        """Doctor marks confirmed appointment as no-show → 200."""
        appt = AppointmentFactory(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.CONFIRMED,
        )
        response = auth_client_doctor.post(f"/api/v1/appointments/{appt.id}/no-show/")
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

        response = client.post(f"/api/v1/appointments/{appt.id}/confirm/")
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

        response = auth_client_patient.get(
            f"/api/v1/doctors/{doctor.id}/available-slots/"
        )
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

        response = auth_client_patient.get(
            f"/api/v1/doctors/{doctor.id}/available-slots/"
        )
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["status"] == TimeSlot.Status.AVAILABLE

    def test_unauthenticated_returns_401(self, db, doctor):
        """Anonymous requests to available-slots → 401."""
        client = APIClient()
        response = client.get(f"/api/v1/doctors/{doctor.id}/available-slots/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_integer_days_returns_400(self, db, auth_client_patient, doctor):
        """A non-integer ?days= value must return 400, not crash with 500."""
        response = auth_client_patient.get(
            f"/api/v1/doctors/{doctor.id}/available-slots/?days=abc"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"


# ---------------------------------------------------------------------------
# TestDoctorList
# ---------------------------------------------------------------------------


class TestDoctorList:
    """GET /api/doctors/ — listing doctors."""

    url = "/api/v1/doctors/"

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

    def test_specialties_count_has_no_n_plus_1(self, db, auth_client_patient):
        """specialties_count must NOT add one query per doctor (N+1 guard).

        Honest measurement: count the real queries when listing 2 doctors,
        then 4 doctors. If specialties_count uses .count() it fires one extra
        COUNT per doctor → query total grows with N → assertion fails.
        With len(prefetch_cache) the total is constant.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from tests.factories import DoctorFactory, SpecialtyFactory

        specialties = [SpecialtyFactory() for _ in range(3)]

        DoctorFactory(specialties=specialties)
        DoctorFactory(specialties=specialties)
        with CaptureQueriesContext(connection) as ctx_two:
            auth_client_patient.get(f"{self.url}?page_size=50")

        DoctorFactory(specialties=specialties)
        DoctorFactory(specialties=specialties)
        with CaptureQueriesContext(connection) as ctx_four:
            auth_client_patient.get(f"{self.url}?page_size=50")

        # Query count must be independent of the number of doctors listed.
        assert len(ctx_two.captured_queries) == len(ctx_four.captured_queries), (
            f"N+1 detected: 2 doctors → {len(ctx_two.captured_queries)} queries, "
            f"4 doctors → {len(ctx_four.captured_queries)} queries"
        )


# ---------------------------------------------------------------------------
# TestAppointmentRetrieve (GET /api/appointments/{id}/)
# ---------------------------------------------------------------------------


class TestAppointmentRetrieve:
    """GET /api/appointments/{id}/ — retrieve single appointment."""

    def test_patient_can_retrieve_own_appointment(
        self, db, auth_client_patient, patient, doctor
    ):
        """Patient retrieves their own appointment → 200 with full detail."""
        appt = AppointmentFactory(patient=patient, doctor=doctor)
        response = auth_client_patient.get(f"/api/v1/appointments/{appt.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(appt.id)
        assert "can_cancel" in response.data
        assert "slot" in response.data

    def test_patient_cannot_retrieve_other_patients_appointment(
        self, db, auth_client_patient, doctor
    ):
        """Patient cannot retrieve another patient's appointment → 404."""
        other_patient = PatientFactory()
        appt = AppointmentFactory(patient=other_patient, doctor=doctor)
        response = auth_client_patient.get(f"/api/v1/appointments/{appt.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_id_returns_404(self, db, auth_client_patient):
        """Non-existent appointment ID returns 404."""
        import uuid

        response = auth_client_patient.get(f"/api/v1/appointments/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_returns_401(self, db, patient, doctor):
        """Unauthenticated request → 401."""
        appt = AppointmentFactory(patient=patient, doctor=doctor)
        client = APIClient()
        response = client.get(f"/api/v1/appointments/{appt.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# TestAppointmentUpdate (PATCH /api/appointments/{id}/)
# ---------------------------------------------------------------------------


class TestAppointmentUpdate:
    """PATCH /api/appointments/{id}/ — update reason."""

    def test_patient_can_update_reason(self, db, auth_client_patient, patient, doctor):
        """Patient updates the reason of their appointment → 200."""
        appt = AppointmentFactory(patient=patient, doctor=doctor, reason="Old reason")
        response = auth_client_patient.patch(
            f"/api/v1/appointments/{appt.id}/",
            {"reason": "New reason"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.reason == "New reason"

    def test_unauthenticated_returns_401(self, db, patient, doctor):
        """Unauthenticated PATCH → 401."""
        appt = AppointmentFactory(patient=patient, doctor=doctor)
        client = APIClient()
        response = client.patch(
            f"/api/v1/appointments/{appt.id}/",
            {"reason": "X"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# TestAppointmentDelete (DELETE /api/appointments/{id}/)
# ---------------------------------------------------------------------------


class TestAppointmentDelete:
    """DELETE /api/appointments/{id}/ — admin only hard delete."""

    def test_admin_can_delete_appointment(self, db, auth_client_admin, patient, doctor):
        """Admin deletes an appointment → 204."""
        appt = AppointmentFactory(patient=patient, doctor=doctor)
        response = auth_client_admin.delete(f"/api/v1/appointments/{appt.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        from apps.appointments.models import Appointment as Appt

        assert not Appt.objects.filter(pk=appt.pk).exists()

    def test_patient_cannot_delete_appointment(
        self, db, auth_client_patient, patient, doctor
    ):
        """Patient cannot delete → 403."""
        appt = AppointmentFactory(patient=patient, doctor=doctor)
        response = auth_client_patient.delete(f"/api/v1/appointments/{appt.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_doctor_cannot_delete_appointment(
        self, db, auth_client_doctor, patient, doctor
    ):
        """Doctor cannot delete → 403 (or 404 — not in their queryset)."""
        other_patient = PatientFactory()
        appt = AppointmentFactory(patient=other_patient, doctor=doctor)
        response = auth_client_doctor.delete(f"/api/v1/appointments/{appt.id}/")
        # Doctor can see this appointment (it's theirs), but destroy requires IsAdminRole
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# TestDoctorDetail (GET /api/doctors/{id}/)
# ---------------------------------------------------------------------------


class TestDoctorDetail:
    """GET /api/doctors/{id}/ — retrieve doctor with full detail."""

    def test_returns_doctor_detail_with_specialties(
        self, db, auth_client_patient, doctor
    ):
        """Detail response includes specialties, email, bio fields."""
        response = auth_client_patient.get(f"/api/v1/doctors/{doctor.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(doctor.id)
        assert "specialties" in response.data
        assert "email" in response.data
        assert "license_number" in response.data

    def test_nonexistent_doctor_returns_404(self, db, auth_client_patient):
        """Non-existent doctor ID → 404."""
        import uuid

        response = auth_client_patient.get(f"/api/v1/doctors/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_returns_401(self, db, doctor):
        """Unauthenticated request → 401."""
        client = APIClient()
        response = client.get(f"/api/v1/doctors/{doctor.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
