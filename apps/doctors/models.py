from django.conf import settings
from django.db import models
from django.utils.translation import gettext, gettext_noop, pgettext_lazy

from apps.core.models import BaseModel
from apps.core.utils import get_display_name

# The names 0003_data_specialties seeds, marked for makemessages. The web
# shows Specialty.display_name; the API keeps the stored English name.
SEEDED_SPECIALTY_NAMES = (
    gettext_noop("Cardiology"),
    gettext_noop("Dermatology"),
    gettext_noop("General Practice"),
    gettext_noop("Neurology"),
    gettext_noop("Pediatrics"),
)


class Specialty(BaseModel):
    """Medical specialty (e.g. Cardiology, Dermatology).

    Read-only via API. Created via data migration.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "Specialty"
        verbose_name_plural = "Specialties"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def display_name(self) -> str:
        """The name in the active language, or as stored if it has no translation."""
        return gettext(self.name)


class Doctor(BaseModel):
    """Medical doctor linked to a User with role='doctor'."""

    # Spanish tells Dr. from Dra.; English says Dr. for both
    class Title(models.TextChoices):
        DR = "dr", pgettext_lazy("doctor title", "Dr.")
        DRA = "dra", pgettext_lazy("female doctor title", "Dr.")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_profile",
    )
    license_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(
        max_length=3,
        choices=Title.choices,
        default=Title.DR,
        help_text="Dr. or Dra. on the Spanish site; English shows Dr. for both.",
    )
    bio = models.TextField(blank=True)
    consultation_duration = models.IntegerField(
        help_text="Duration in minutes", default=30
    )
    specialties = models.ManyToManyField(Specialty, related_name="doctors", blank=True)

    class Meta:
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"

    def __str__(self) -> str:
        return f"{self.get_title_display()} {get_display_name(self.user)}"


class Schedule(BaseModel):
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
