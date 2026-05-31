"""Management command: generate_slots.

Generates TimeSlot objects for all active schedules (or a specific doctor)
over a configurable number of days ahead.

Usage:
    python manage.py generate_slots
    python manage.py generate_slots --days=30
    python manage.py generate_slots --doctor-id=<uuid>
"""

from django.core.management.base import BaseCommand

from apps.appointments.services import generate_slots_for_schedule
from apps.doctors.models import Schedule


class Command(BaseCommand):
    help = "Generate appointment slots for all active schedules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days ahead to generate slots for (default: 7).",
        )
        parser.add_argument(
            "--doctor-id",
            dest="doctor_id",
            type=str,
            default=None,
            help="Generate slots for a specific doctor UUID only.",
        )

    def handle(self, *args, **options):
        days_ahead = options["days"]
        doctor_id = options["doctor_id"]

        schedules = Schedule.objects.filter(is_active=True).select_related(
            "doctor__user"
        )
        if doctor_id:
            schedules = schedules.filter(doctor__id=doctor_id)

        total_slots = 0
        total_schedules = 0

        for schedule in schedules:
            slots = generate_slots_for_schedule(schedule, days_ahead=days_ahead)
            count = len(slots)
            total_slots += count
            total_schedules += 1
            self.stdout.write(
                f"  Schedule {schedule.pk} "
                f"(Dr. {schedule.doctor.user.email}): {count} slots"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_slots} slots generated "
                f"across {total_schedules} schedule(s)."
            )
        )
