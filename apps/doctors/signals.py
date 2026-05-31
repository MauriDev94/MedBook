"""Signal handlers for the doctors app.

Registered in DoctorsConfig.ready() — never import this module directly.
"""

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.doctors.models import Schedule

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Schedule)
def generate_initial_slots(sender, instance, created, **kwargs):
    """Generate TimeSlots automatically when a new Schedule is created.

    Only runs on creation (created=True). Updates to an existing Schedule
    do NOT regenerate slots — that would create duplicates.

    Error handling strategy:
    - Expected errors (ValidationError, IntegrityError) → logged as ERROR
    - Unexpected errors → logged as EXCEPTION (includes full traceback)
    - Neither is re-raised — the Schedule save must always succeed.
    """
    if not created:
        return

    # Late import to avoid circular dependency:
    # doctors.signals → appointments.services → appointments.models
    from apps.appointments.services import generate_slots_for_schedule

    try:
        generate_slots_for_schedule(instance, days_ahead=7)
    except (ValidationError, IntegrityError) as exc:
        logger.error(
            "Failed to generate slots for schedule %s: %s",
            instance.pk,
            exc,
        )
    except Exception:
        logger.exception(
            "Unexpected error generating slots for schedule %s",
            instance.pk,
        )
