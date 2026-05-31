"""Business logic for the appointments domain.

All functions here are pure Python — no HTTP, no serializers.
ViewSets call these functions; they never touch the ORM directly.

Atomic transactions: functions that modify multiple models are wrapped
with @transaction.atomic to guarantee consistency (e.g. cancel must
update both the appointment AND the slot in one transaction).
"""

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment, TimeSlot


@transaction.atomic
def create_appointment(
    patient, doctor, slot: TimeSlot, reason: str = ""
) -> Appointment:
    """Create an appointment and atomically reserve the slot.

    Uses an atomic UPDATE on the slot to prevent race conditions: if two
    requests try to book the same slot simultaneously, only one UPDATE
    will match (status=AVAILABLE), and the other will raise ValidationError.

    Args:
        patient: Patient instance (from request.user.patient_profile).
        doctor: Doctor instance (inferred from slot.schedule.doctor).
        slot: TimeSlot to reserve.
        reason: Optional reason for the appointment.

    Returns:
        The created Appointment instance.

    Raises:
        ValidationError: if the slot was taken between validation and creation.
    """
    updated = TimeSlot.objects.filter(
        id=slot.id, status=TimeSlot.Status.AVAILABLE
    ).update(status=TimeSlot.Status.RESERVED, updated_at=timezone.now())

    if not updated:
        raise ValidationError("This time slot is no longer available.")

    slot.refresh_from_db()
    return Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        slot=slot,
        reason=reason,
    )


def validate_appointment_booking(patient, slot: TimeSlot) -> None:
    """Validate business rules before creating an appointment.

    Raises:
        ValidationError: if the slot is unavailable or the patient
                         already has a conflicting active appointment.

    Called by: AppointmentCreateSerializer.validate()
    """
    if slot.status != TimeSlot.Status.AVAILABLE:
        raise ValidationError("This time slot is no longer available.")

    has_conflict = Appointment.objects.filter(
        patient=patient,
        slot__start_datetime__lt=slot.end_datetime,
        slot__end_datetime__gt=slot.start_datetime,
        status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
    ).exists()

    if has_conflict:
        raise ValidationError("You already have an appointment at this time.")


@transaction.atomic
def confirm_appointment(appointment: Appointment, confirmed_by) -> Appointment:
    """Transition a PENDING appointment to CONFIRMED.

    Args:
        appointment: The Appointment instance to confirm.
        confirmed_by: User performing the action (for audit trail).

    Returns:
        The updated Appointment instance.

    Raises:
        ValueError: if the appointment is not in PENDING status.
    """
    appointment.confirm()  # raises ValueError if invalid transition
    return appointment


@transaction.atomic
def cancel_appointment(appointment: Appointment, cancelled_by) -> Appointment:
    """Cancel an appointment and free the associated time slot.

    Cancellation is allowed from PENDING or CONFIRMED status.
    The slot is returned to AVAILABLE so it can be booked again.

    Args:
        appointment: The Appointment instance to cancel.
        cancelled_by: User performing the action (patient, doctor, or admin).

    Returns:
        The updated Appointment instance.

    Raises:
        ValueError: if the appointment cannot be cancelled (e.g. COMPLETED).
    """
    appointment.cancel()  # raises ValueError if invalid transition

    appointment.slot.status = TimeSlot.Status.AVAILABLE
    appointment.slot.save(update_fields=["status", "updated_at"])

    return appointment


@transaction.atomic
def complete_appointment(appointment: Appointment) -> Appointment:
    """Transition a CONFIRMED appointment to COMPLETED.

    Returns:
        The updated Appointment instance.

    Raises:
        ValueError: if the appointment is not CONFIRMED.
    """
    appointment.complete()  # raises ValueError if invalid transition
    return appointment


@transaction.atomic
def mark_no_show(appointment: Appointment) -> Appointment:
    """Mark a CONFIRMED appointment as NO_SHOW when the patient doesn't attend.

    Returns:
        The updated Appointment instance.

    Raises:
        ValueError: if the appointment is not CONFIRMED.
    """
    appointment.mark_no_show()  # raises ValueError if invalid transition
    return appointment


def generate_slots_for_schedule(schedule, days_ahead: int = 7) -> list[TimeSlot]:
    """Generate TimeSlot objects for a schedule over the next N days.

    Only creates slots for the schedule's day_of_week. Slots are created
    at intervals of doctor.consultation_duration minutes between
    schedule.start_time and schedule.end_time.

    Uses bulk_create(ignore_conflicts=True) so running this twice is safe
    (idempotent — no duplicate slots are created).

    Args:
        schedule: A Schedule instance with day_of_week, start_time, end_time.
        days_ahead: How many days into the future to generate slots for.

    Returns:
        List of TimeSlot objects that were successfully created.
    """
    if days_ahead <= 0:
        return []

    duration = datetime.timedelta(minutes=schedule.doctor.consultation_duration)
    today = timezone.localdate()
    slots_to_create = []

    for offset in range(days_ahead):
        candidate_date = today + datetime.timedelta(days=offset)
        # Skip days that don't match the schedule's weekday
        if candidate_date.weekday() != schedule.day_of_week:
            continue

        # Walk through the schedule window in consultation_duration steps
        current = datetime.datetime.combine(
            candidate_date,
            schedule.start_time,
            tzinfo=datetime.timezone.utc,
        )
        end_of_day = datetime.datetime.combine(
            candidate_date,
            schedule.end_time,
            tzinfo=datetime.timezone.utc,
        )

        while current + duration <= end_of_day:
            slots_to_create.append(
                TimeSlot(
                    schedule=schedule,
                    start_datetime=current,
                    end_datetime=current + duration,
                    status=TimeSlot.Status.AVAILABLE,
                )
            )
            current += duration

    created = TimeSlot.objects.bulk_create(
        slots_to_create,
        ignore_conflicts=True,
    )
    return list(created)
