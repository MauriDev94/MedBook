from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TimeSlot(BaseModel):
    """Concrete time slot generated from a doctor's schedule.

    One slot represents a single appointment window. Slots are created
    by a signal (post_save on Schedule) or by the generate_slots command.
    """

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        BLOCKED = "blocked", "Blocked"

    schedule = models.ForeignKey(
        "doctors.Schedule",
        on_delete=models.CASCADE,
        related_name="time_slots",
    )
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    class Meta:
        verbose_name = "Time Slot"
        verbose_name_plural = "Time Slots"
        ordering = ["start_datetime"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "start_datetime"],
                name="unique_slot_per_schedule_and_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.schedule.doctor} - {self.start_datetime:%Y-%m-%d %H:%M}"


class Appointment(BaseModel):
    """A medical appointment between a patient and a doctor.

    Manages its own status transitions via model methods. Business logic
    that involves multiple models (e.g. booking validation) lives in services.py.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No Show"

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        "doctors.Doctor",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    slot = models.OneToOneField(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="appointment",
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.patient} ↔ {self.doctor} @ {self.slot.start_datetime:%Y-%m-%d %H:%M}"

    # ------------------------------------------------------------------
    # Status machine — transition checks
    # ------------------------------------------------------------------

    def can_be_confirmed(self) -> bool:
        """Appointment can be confirmed only when pending."""
        return self.status == self.Status.PENDING

    def can_be_cancelled(self) -> bool:
        """Appointment can be cancelled from pending or confirmed."""
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)

    def can_be_completed(self) -> bool:
        """Appointment can be completed only when confirmed."""
        return self.status == self.Status.CONFIRMED

    def can_be_marked_no_show(self) -> bool:
        """Appointment can be marked no-show only when confirmed."""
        return self.status == self.Status.CONFIRMED

    # ------------------------------------------------------------------
    # Status machine — transitions
    # ------------------------------------------------------------------

    def confirm(self) -> None:
        """Transition from pending to confirmed."""
        if not self.can_be_confirmed():
            raise ValueError(f"Cannot confirm appointment in status '{self.status}'")
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])

    def cancel(self) -> None:
        """Transition from pending or confirmed to cancelled."""
        if not self.can_be_cancelled():
            raise ValueError(f"Cannot cancel appointment in status '{self.status}'")
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

    def complete(self) -> None:
        """Transition from confirmed to completed."""
        if not self.can_be_completed():
            raise ValueError(f"Cannot complete appointment in status '{self.status}'")
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status", "updated_at"])

    def mark_no_show(self) -> None:
        """Transition from confirmed to no_show."""
        if not self.can_be_marked_no_show():
            raise ValueError(
                f"Cannot mark no-show appointment in status '{self.status}'"
            )
        self.status = self.Status.NO_SHOW
        self.save(update_fields=["status", "updated_at"])


class MedicalNote(BaseModel):
    """Clinical note attached to an appointment.

    Only the doctor assigned to the appointment (or an admin) can
    create and view notes.
    """

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="medical_notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medical_notes",
    )
    content = models.TextField()

    class Meta:
        verbose_name = "Medical Note"
        verbose_name_plural = "Medical Notes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Note by {self.author.email} on {self.appointment}"
