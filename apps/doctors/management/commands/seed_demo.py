"""Management command: seed_demo.

Creates the demo doctors and their weekly schedules (apps.doctors.demo)
when MEDBOOK_DEMO_DATA is true, and does nothing otherwise. Idempotent:
safe to run on every deploy startup, before generate_slots.

Usage:
    python manage.py seed_demo
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.doctors.services import seed_demo_doctors


class Command(BaseCommand):
    help = "Creates the demo doctors when MEDBOOK_DEMO_DATA is true. Idempotent."

    def handle(self, *args, **options):
        if not settings.DEMO_DATA:
            self.stdout.write(
                self.style.WARNING("MEDBOOK_DEMO_DATA is not true — skipping.")
            )
            return

        doctors = seed_demo_doctors()
        for doctor in doctors:
            self.stdout.write(f"  {doctor} ({doctor.user.email})")
        self.stdout.write(
            self.style.SUCCESS(f"Done. {len(doctors)} demo doctor(s) created.")
        )
