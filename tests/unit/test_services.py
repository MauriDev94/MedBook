"""Tests for apps/appointments/services.py.

Coverage target: ≥ 90% in services.py.

Pattern: each service function gets tests for:
  - happy path (valid input → expected state change)
  - guard/validation failures (invalid state → raises exception)
  - side effects (slot status, DB persistence)
"""

import pytest
from django.core.exceptions import ValidationError

from apps.appointments import services
from apps.appointments.models import Appointment, TimeSlot
from tests.factories import (
    AppointmentFactory,
    PatientFactory,
    ScheduleFactory,
    TimeSlotFactory,
)


# ---------------------------------------------------------------------------
# validate_appointment_booking
# ---------------------------------------------------------------------------


class TestValidateAppointmentBooking:
    """Validates business rules before creating an appointment."""

    def test_available_slot_with_no_conflicts_passes(self, db):
        """Valid booking: slot is available and patient has no overlap."""
        patient = PatientFactory()
        slot = TimeSlotFactory(status=TimeSlot.Status.AVAILABLE)
        # Should NOT raise — no exception means success
        services.validate_appointment_booking(patient, slot)

    def test_reserved_slot_raises(self, db):
        """Slot already reserved → ValidationError."""
        patient = PatientFactory()
        slot = TimeSlotFactory(status=TimeSlot.Status.RESERVED)
        with pytest.raises(ValidationError, match="no longer available"):
            services.validate_appointment_booking(patient, slot)

    def test_blocked_slot_raises(self, db):
        """Blocked slot → ValidationError."""
        patient = PatientFactory()
        slot = TimeSlotFactory(status=TimeSlot.Status.BLOCKED)
        with pytest.raises(ValidationError, match="no longer available"):
            services.validate_appointment_booking(patient, slot)

    def test_overlapping_pending_appointment_raises(self, db):
        """Patient already has a PENDING appointment at the same time → ValidationError."""
        patient = PatientFactory()
        existing = AppointmentFactory(
            patient=patient,
            status=Appointment.Status.PENDING,
        )
        # New slot overlaps with existing appointment's slot
        overlapping_slot = TimeSlotFactory(
            start_datetime=existing.slot.start_datetime,
            end_datetime=existing.slot.end_datetime,
            status=TimeSlot.Status.AVAILABLE,
        )
        with pytest.raises(ValidationError, match="already have an appointment"):
            services.validate_appointment_booking(patient, overlapping_slot)

    def test_overlapping_confirmed_appointment_raises(self, db):
        """Patient with CONFIRMED appointment at same time → ValidationError."""
        patient = PatientFactory()
        existing = AppointmentFactory(
            patient=patient,
            status=Appointment.Status.CONFIRMED,
        )
        overlapping_slot = TimeSlotFactory(
            start_datetime=existing.slot.start_datetime,
            end_datetime=existing.slot.end_datetime,
            status=TimeSlot.Status.AVAILABLE,
        )
        with pytest.raises(ValidationError, match="already have an appointment"):
            services.validate_appointment_booking(patient, overlapping_slot)

    def test_cancelled_appointment_does_not_block_rebooking(self, db):
        """Cancelled appointment at same time should NOT block new booking."""
        patient = PatientFactory()
        cancelled = AppointmentFactory(
            patient=patient,
            status=Appointment.Status.CANCELLED,
        )
        new_slot = TimeSlotFactory(
            start_datetime=cancelled.slot.start_datetime,
            end_datetime=cancelled.slot.end_datetime,
            status=TimeSlot.Status.AVAILABLE,
        )
        # Should NOT raise — cancelled doesn't block
        services.validate_appointment_booking(patient, new_slot)

    def test_completed_appointment_does_not_block_rebooking(self, db):
        """Completed appointment at same time should NOT block a new booking."""
        patient = PatientFactory()
        completed = AppointmentFactory(
            patient=patient,
            status=Appointment.Status.COMPLETED,
        )
        new_slot = TimeSlotFactory(
            start_datetime=completed.slot.start_datetime,
            end_datetime=completed.slot.end_datetime,
            status=TimeSlot.Status.AVAILABLE,
        )
        # COMPLETED is not PENDING/CONFIRMED → should not block
        services.validate_appointment_booking(patient, new_slot)

    def test_no_show_appointment_does_not_block_rebooking(self, db):
        """NO_SHOW appointment at same time should NOT block a new booking."""
        patient = PatientFactory()
        no_show = AppointmentFactory(
            patient=patient,
            status=Appointment.Status.NO_SHOW,
        )
        new_slot = TimeSlotFactory(
            start_datetime=no_show.slot.start_datetime,
            end_datetime=no_show.slot.end_datetime,
            status=TimeSlot.Status.AVAILABLE,
        )
        # NO_SHOW is not PENDING/CONFIRMED → should not block
        services.validate_appointment_booking(patient, new_slot)


# ---------------------------------------------------------------------------
# confirm_appointment
# ---------------------------------------------------------------------------


class TestConfirmAppointment:
    """Transitions an appointment from PENDING → CONFIRMED."""

    def test_confirm_pending_changes_status_to_confirmed(self, db):
        """Happy path: pending appointment becomes confirmed."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        services.confirm_appointment(appt, confirmed_by=appt.doctor.user)
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CONFIRMED

    def test_confirm_persists_to_db(self, db):
        """Status change is saved — not just in-memory."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        services.confirm_appointment(appt, confirmed_by=appt.doctor.user)
        fresh = Appointment.objects.get(pk=appt.pk)
        assert fresh.status == Appointment.Status.CONFIRMED

    def test_confirm_already_confirmed_raises(self, db):
        """Confirming an already-confirmed appointment raises ValueError."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        with pytest.raises(ValueError):
            services.confirm_appointment(appt, confirmed_by=appt.doctor.user)

    def test_confirm_cancelled_raises(self, db):
        """Confirming a cancelled appointment raises ValueError."""
        appt = AppointmentFactory(status=Appointment.Status.CANCELLED)
        with pytest.raises(ValueError):
            services.confirm_appointment(appt, confirmed_by=appt.doctor.user)

    def test_confirm_returns_appointment(self, db):
        """Service returns the updated appointment object."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        result = services.confirm_appointment(appt, confirmed_by=appt.doctor.user)
        assert result == appt


# ---------------------------------------------------------------------------
# cancel_appointment
# ---------------------------------------------------------------------------


class TestCancelAppointment:
    """Cancels an appointment and frees the associated slot."""

    def test_cancel_pending_changes_status(self, db):
        """Pending appointment can be cancelled."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        services.cancel_appointment(appt, cancelled_by=appt.patient.user)
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED

    def test_cancel_confirmed_changes_status(self, db):
        """Confirmed appointment can be cancelled."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        services.cancel_appointment(appt, cancelled_by=appt.doctor.user)
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED

    def test_cancel_frees_the_slot(self, db):
        """Cancellation sets the slot back to AVAILABLE."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        # Mark slot as reserved (simulating a real booking)
        appt.slot.status = TimeSlot.Status.RESERVED
        appt.slot.save(update_fields=["status", "updated_at"])

        services.cancel_appointment(appt, cancelled_by=appt.patient.user)

        appt.slot.refresh_from_db()
        assert appt.slot.status == TimeSlot.Status.AVAILABLE

    def test_cancel_completed_raises(self, db):
        """Completed appointment cannot be cancelled."""
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError):
            services.cancel_appointment(appt, cancelled_by=appt.patient.user)

    def test_cancel_returns_appointment(self, db):
        """Service returns the updated appointment object."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        result = services.cancel_appointment(appt, cancelled_by=appt.patient.user)
        assert result == appt


# ---------------------------------------------------------------------------
# complete_appointment
# ---------------------------------------------------------------------------


class TestCompleteAppointment:
    """Transitions CONFIRMED → COMPLETED."""

    def test_complete_confirmed_changes_status(self, db):
        """Confirmed appointment becomes completed."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        services.complete_appointment(appt)
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.COMPLETED

    def test_complete_persists_to_db(self, db):
        """Status change is saved to the DB."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        services.complete_appointment(appt)
        fresh = Appointment.objects.get(pk=appt.pk)
        assert fresh.status == Appointment.Status.COMPLETED

    def test_complete_pending_raises(self, db):
        """Cannot complete a pending appointment."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError):
            services.complete_appointment(appt)

    def test_complete_returns_appointment(self, db):
        """Service returns the updated appointment."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        result = services.complete_appointment(appt)
        assert result == appt


# ---------------------------------------------------------------------------
# mark_no_show
# ---------------------------------------------------------------------------


class TestMarkNoShow:
    """Transitions CONFIRMED → NO_SHOW."""

    def test_mark_no_show_confirmed_changes_status(self, db):
        """Confirmed appointment becomes no_show."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        services.mark_no_show(appt)
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.NO_SHOW

    def test_mark_no_show_persists_to_db(self, db):
        """Status change is saved to the DB."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        services.mark_no_show(appt)
        fresh = Appointment.objects.get(pk=appt.pk)
        assert fresh.status == Appointment.Status.NO_SHOW

    def test_mark_no_show_pending_raises(self, db):
        """Cannot mark pending appointment as no_show."""
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError):
            services.mark_no_show(appt)

    def test_mark_no_show_returns_appointment(self, db):
        """Service returns the updated appointment."""
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        result = services.mark_no_show(appt)
        assert result == appt


# ---------------------------------------------------------------------------
# generate_slots_for_schedule
# ---------------------------------------------------------------------------


class TestGenerateSlotsForSchedule:
    """Generates TimeSlot objects for a given schedule."""

    def test_generates_slots_for_correct_weekday(self, db):
        """Slots are created only for the schedule's day_of_week."""
        from apps.doctors.models import Schedule

        schedule = ScheduleFactory(day_of_week=Schedule.DayOfWeek.MONDAY)
        slots = services.generate_slots_for_schedule(schedule, days_ahead=14)
        assert len(slots) > 0
        for slot in slots:
            assert slot.start_datetime.weekday() == 0  # Monday = 0

    def test_generates_slots_within_schedule_hours(self, db):
        """All generated slots fall within start_time and end_time."""
        import datetime

        schedule = ScheduleFactory(
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        slots = services.generate_slots_for_schedule(schedule, days_ahead=14)
        assert len(slots) > 0
        for slot in slots:
            slot_time = slot.start_datetime.time()
            assert slot_time >= schedule.start_time
            assert slot_time < schedule.end_time

    def test_slot_duration_matches_consultation_duration(self, db):
        """Each slot's duration equals doctor's consultation_duration."""
        from datetime import timedelta

        schedule = ScheduleFactory()
        duration = schedule.doctor.consultation_duration
        slots = services.generate_slots_for_schedule(schedule, days_ahead=14)
        assert len(slots) > 0
        for slot in slots:
            delta = slot.end_datetime - slot.start_datetime
            assert delta == timedelta(minutes=duration)

    def test_no_duplicate_slots_on_rerun(self, db):
        """Running twice does not create duplicate slots (ignore_conflicts)."""
        schedule = ScheduleFactory()
        first_run = services.generate_slots_for_schedule(schedule, days_ahead=7)
        second_run = services.generate_slots_for_schedule(schedule, days_ahead=7)
        total = TimeSlot.objects.filter(schedule=schedule).count()
        assert total == len(first_run)  # second run added nothing
        # Second run returns empty or same count — no duplicates in DB
        _ = second_run  # suppress unused variable

    def test_returns_list_of_timeslot_objects(self, db):
        """Return value is a list of TimeSlot instances."""
        schedule = ScheduleFactory()
        slots = services.generate_slots_for_schedule(schedule, days_ahead=14)
        assert isinstance(slots, list)
        assert all(isinstance(s, TimeSlot) for s in slots)

    def test_zero_days_ahead_returns_empty(self, db):
        """days_ahead=0 generates no slots."""
        schedule = ScheduleFactory()
        slots = services.generate_slots_for_schedule(schedule, days_ahead=0)
        assert slots == []

    def test_days_ahead_1_with_wrong_weekday_returns_empty(self, db):
        """days_ahead=1 when today+1 doesn't match schedule day → empty list."""
        import datetime
        from unittest.mock import patch

        from apps.doctors.models import Schedule

        # Schedule is Monday; patch today so tomorrow is Tuesday (no match)
        # weekday 0=Mon,1=Tue — if today is Monday (0), tomorrow is Tuesday (1)
        # We need today to NOT be Sunday (so tomorrow is Monday)
        # Use a known Monday as "today" → tomorrow is Tuesday → no Monday in 1 day
        monday = datetime.date(2026, 6, 1)  # This is a Monday
        schedule = ScheduleFactory(day_of_week=Schedule.DayOfWeek.MONDAY)

        with patch("apps.appointments.services.timezone") as mock_tz:
            mock_tz.localdate.return_value = monday
            # days_ahead=1 → only checks 2026-06-01 (Monday itself)
            # BUT: range(1) = [0], candidate = monday+0 = Monday → DOES match
            # So use days_ahead=1 starting from Tuesday
            tuesday = datetime.date(2026, 6, 2)
            mock_tz.localdate.return_value = tuesday
            slots = services.generate_slots_for_schedule(schedule, days_ahead=1)

        assert slots == []  # Tuesday doesn't match MONDAY schedule


# ---------------------------------------------------------------------------
# create_appointment
# ---------------------------------------------------------------------------


class TestCreateAppointment:
    """Atomically creates an appointment and reserves the slot."""

    def test_creates_appointment_and_reserves_slot(self, db):
        """Happy path: appointment created, slot becomes RESERVED."""
        patient = PatientFactory()
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        slot = TimeSlotFactory(status=TimeSlot.Status.AVAILABLE)
        doctor = appt.doctor

        result = services.create_appointment(patient, doctor, slot, reason="Test")
        slot.refresh_from_db()
        assert result.patient == patient
        assert result.doctor == doctor
        assert slot.status == TimeSlot.Status.RESERVED

    def test_raises_if_slot_already_reserved(self, db):
        """If slot becomes reserved between validation and creation → ValidationError."""
        patient = PatientFactory()
        appt = AppointmentFactory()
        slot = TimeSlotFactory(status=TimeSlot.Status.RESERVED)

        from django.core.exceptions import ValidationError as DjangoValidationError

        with pytest.raises(DjangoValidationError):
            services.create_appointment(patient, appt.doctor, slot)
