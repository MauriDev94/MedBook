import uuid

from django.conf import settings
from django.db import models


class Specialty(models.Model):
    """Medical specialty (e.g. Cardiology, Dermatology).

    Read-only via API. Created via data migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "Specialty"
        verbose_name_plural = "Specialties"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Doctor(models.Model):
    """Medical doctor linked to a User with role='doctor'."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_profile",
    )
    license_number = models.CharField(max_length=50, unique=True)
    bio = models.TextField(blank=True)
    consultation_duration = models.IntegerField(
        help_text="Duration in minutes", default=30
    )
    specialties = models.ManyToManyField(
        Specialty, related_name="doctors", blank=True
    )

    class Meta:
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"

    def __str__(self) -> str:
        return f"Dr. {self.user.full_name or self.user.email}"


class Schedule(models.Model):
    """Recurring weekly availability for a doctor.

    A Schedule defines the hours a doctor is available on a given day of the week.
    Concrete TimeSlot instances are generated from these schedules.
    """

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        Doctor, on_delete=models.CASCADE, related_name="schedules"
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"
        ordering = ["doctor", "day_of_week", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "day_of_week", "start_time"],
                name="unique_schedule_per_doctor_day_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.doctor} - {self.get_day_of_week_display()} ({self.start_time}-{self.end_time})"
