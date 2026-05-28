from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Patient(BaseModel):
    """Patient linked to a User with role='patient'."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self) -> str:
        return self.user.full_name or self.user.email
