from django.db import migrations
from django.utils import timezone


# The demo doctors that apps/doctors/demo.py marks as Dra. seed_demo never
# changes existing rows, so the ones dev and production already have get
# their title here. A database without them is left as it is.
DRA_LICENSES = ("DEMO-001", "DEMO-003", "DEMO-005")


def set_demo_doctors_title(apps, schema_editor):
    """Give "Dra." to Carla Soto, Valentina Rojas and Camila Herrera."""
    Doctor = apps.get_model("doctors", "Doctor")
    Doctor.objects.filter(license_number__in=DRA_LICENSES).update(
        title="dra", updated_at=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("doctors", "0005_doctor_title"),
    ]

    operations = [
        migrations.RunPython(
            set_demo_doctors_title, reverse_code=migrations.RunPython.noop
        ),
    ]
