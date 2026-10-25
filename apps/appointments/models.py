from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class TimeSlot(BaseModel):
    """Concrete available slot generated from a doctor's Schedule.

    One TimeSlot = one bookable block of time. A slot keeps every
    appointment ever booked on it (cancelled, completed, no-show), but at
    most one active one (pending or confirmed), so it cannot be
    double-booked. See docs/adr/0004-slot-appointment-history.md.
    """

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        BLOCKED = "blocked", "Blocked"

    schedule = models.ForeignKey(
        "doctors.Schedule",
        on_delete=models.CASCADE,
        related_name="slots",
    )
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    class Meta:
        verbose_name = "Time Slot"
        verbose_name_plural = "Time Slots"
        ordering = ["start_datetime"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "start_datetime"],
                name="unique_slot_per_schedule_start",
            )
        ]

    def __str__(self) -> str:
        return f"{self.schedule.doctor} | {self.start_datetime:%Y-%m-%d %H:%M} [{self.status}]"

    @property
    def has_started(self) -> bool:
        return self.start_datetime <= timezone.now()


ONE_ACTIVE_APPOINTMENT_PER_SLOT = "one_active_appointment_per_slot"


class InvalidTransition(ValueError):
    """Raised when an Appointment state transition is not allowed.

    Subclass of ValueError so existing `except ValueError` call sites keep
    working unchanged; the custom exception handler maps it to a 400.
    """


class Appointment(BaseModel):
    """A booking linking a patient, a doctor, and a concrete TimeSlot.

    Follows a strict state machine — transitions are enforced via model
    methods. Invalid transitions raise ValueError.
    """

    # Lazy labels: the web shows them translated; the API sends the values
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        CONFIRMED = "confirmed", _("Confirmed")
        CANCELLED = "cancelled", _("Cancelled")
        COMPLETED = "completed", _("Completed")
        NO_SHOW = "no_show", _("No Show")

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        "doctors.Doctor",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ["-created_at"]
        constraints = [
            # A slot keeps its history but holds one active appointment at most
            models.UniqueConstraint(
                fields=["slot"],
                condition=models.Q(status__in=["pending", "confirmed"]),
                name=ONE_ACTIVE_APPOINTMENT_PER_SLOT,
            )
        ]

    def __str__(self) -> str:
        return f"{self.patient} → {self.doctor} [{self.status}]"

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def can_be_confirmed(self) -> bool:
        return self.status == self.Status.PENDING

    def can_be_cancelled(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)

    def can_be_completed(self) -> bool:
        return self.status == self.Status.CONFIRMED

    def can_be_marked_no_show(self) -> bool:
        return self.status == self.Status.CONFIRMED

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def confirm(self) -> None:
        """pending → confirmed. Raises InvalidTransition if invalid."""
        if not self.can_be_confirmed():
            raise InvalidTransition(
                f"Cannot confirm appointment with status '{self.status}'."
            )
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])

    def cancel(self) -> None:
        """pending|confirmed → cancelled. Raises InvalidTransition if invalid."""
        if not self.can_be_cancelled():
            raise InvalidTransition(
                f"Cannot cancel appointment with status '{self.status}'."
            )
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

    def complete(self) -> None:
        """confirmed → completed. Raises InvalidTransition if invalid."""
        if not self.can_be_completed():
            raise InvalidTransition(
                f"Cannot complete appointment with status '{self.status}'."
            )
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status", "updated_at"])

    def mark_no_show(self) -> None:
        """confirmed → no_show. Raises InvalidTransition if invalid."""
        if not self.can_be_marked_no_show():
            raise InvalidTransition(
                f"Cannot mark as no-show appointment with status '{self.status}'."
            )
        self.status = self.Status.NO_SHOW
        self.save(update_fields=["status", "updated_at"])


class MedicalNote(BaseModel):
    """Clinical note written by a doctor after an appointment."""

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medical_notes",
    )
    content = models.TextField()

    class Meta:
        verbose_name = "Medical Note"
        verbose_name_plural = "Medical Notes"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Note by {self.author} on {self.appointment}"
