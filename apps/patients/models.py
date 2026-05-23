import uuid

from django.conf import settings
from django.db import models


class Patient(models.Model):
    """Patient linked to a User with role='patient'."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
