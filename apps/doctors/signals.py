"""Signal handlers for the doctors app.

Registered in DoctorsConfig.ready() — never import this module directly.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.doctors.models import Schedule

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Schedule)
def generate_initial_slots(sender, instance, created, **kwargs):
    """Generate TimeSlots automatically when a new Schedule is created.

    Only runs on creation (created=True). Updates to an existing Schedule
    do NOT regenerate slots — that would create duplicates.

    If slot generation fails for any reason, the error is logged but NOT
    re-raised. The Schedule save must always succeed; slot generation is
    a side effect, not part of the main transaction.
    """
    if not created:
        return

    # Late import to avoid circular dependency:
    # doctors.signals → appointments.services → appointments.models
    from apps.appointments.services import generate_slots_for_schedule

    try:
        generate_slots_for_schedule(instance, days_ahead=7)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to generate slots for schedule %s: %s",
            instance.pk,
            exc,
        )
