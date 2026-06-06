"""Management command: ensure_superuser.

Creates an admin superuser from environment variables if none exists.
Idempotent — safe to run on every deploy startup.

Required env vars:
    DJANGO_SUPERUSER_EMAIL    — email for the superuser account
    DJANGO_SUPERUSER_PASSWORD — password for the superuser account
"""

from decouple import config
from django.core.management.base import BaseCommand

from apps.users.models import Role, User


class Command(BaseCommand):
    help = "Creates an admin superuser from env vars if none exists. Idempotent."

    def handle(self, *args, **options):
        email = config("DJANGO_SUPERUSER_EMAIL", default="")
        password = config("DJANGO_SUPERUSER_PASSWORD", default="")

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD not set — skipping."
                )
            )
            return

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS("Superuser already exists — skipping.")
            )
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            role=Role.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser created: {email}"))
