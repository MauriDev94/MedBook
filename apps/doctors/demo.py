"""Demo doctors that seed_demo creates when MEDBOOK_DEMO_DATA is true.

Fictional people: emails on the reserved medbook.example domain (RFC 2606)
and DEMO- license numbers. Hours are Chilean time (TIME_ZONE, ADR 0003).
The bios are profile text, shown as stored, so they are in Spanish, the
web's default language.
"""

import datetime
from dataclasses import dataclass

from apps.doctors.models import Schedule

Day = Schedule.DayOfWeek


@dataclass(frozen=True)
class DemoDoctor:
    first_name: str
    last_name: str
    email: str
    license_number: str
    specialty_slugs: tuple[str, ...]
    consultation_duration: int
    bio: str
    # (day_of_week, start_time, end_time), one Schedule each
    hours: tuple[tuple[int, datetime.time, datetime.time], ...]


def weekly(days, start: str, end: str) -> tuple:
    """The same start–end hours on each of `days`."""
    start_time = datetime.time.fromisoformat(start)
    end_time = datetime.time.fromisoformat(end)
    return tuple((day, start_time, end_time) for day in days)


DEMO_DOCTORS = (
    DemoDoctor(
        first_name="Carla",
        last_name="Soto",
        email="carla.soto@medbook.example",
        license_number="DEMO-001",
        specialty_slugs=("cardiology",),
        consultation_duration=30,
        bio="Cardióloga. Controles preventivos y seguimiento de hipertensión.",
        hours=weekly((Day.MONDAY, Day.WEDNESDAY), "09:00", "13:00"),
    ),
    DemoDoctor(
        first_name="Matías",
        last_name="Fuentes",
        email="matias.fuentes@medbook.example",
        license_number="DEMO-002",
        specialty_slugs=("dermatology",),
        consultation_duration=30,
        bio="Dermatólogo. Acné, lunares y control de manchas en la piel.",
        hours=weekly((Day.TUESDAY, Day.THURSDAY), "10:00", "14:00"),
    ),
    DemoDoctor(
        first_name="Valentina",
        last_name="Rojas",
        email="valentina.rojas@medbook.example",
        license_number="DEMO-003",
        specialty_slugs=("pediatrics",),
        consultation_duration=30,
        bio="Pediatra. Control sano del niño y vacunas.",
        hours=weekly((Day.MONDAY, Day.TUESDAY, Day.FRIDAY), "14:00", "18:00"),
    ),
    DemoDoctor(
        first_name="Joaquín",
        last_name="Muñoz",
        email="joaquin.munoz@medbook.example",
        license_number="DEMO-004",
        specialty_slugs=("neurology",),
        consultation_duration=45,
        bio="Neurólogo. Cefaleas, mareos y trastornos del sueño.",
        hours=weekly((Day.WEDNESDAY, Day.FRIDAY), "09:00", "12:00"),
    ),
    DemoDoctor(
        first_name="Camila",
        last_name="Herrera",
        email="camila.herrera@medbook.example",
        license_number="DEMO-005",
        specialty_slugs=("general-practice",),
        consultation_duration=20,
        bio="Medicina general. Consultas de morbilidad y chequeos anuales.",
        hours=weekly(Day.values[:5], "08:30", "12:30"),
    ),
    DemoDoctor(
        first_name="Felipe",
        last_name="Araya",
        email="felipe.araya@medbook.example",
        license_number="DEMO-006",
        specialty_slugs=("general-practice", "pediatrics"),
        consultation_duration=30,
        bio="Médico de familia. Atiende niños y adultos.",
        hours=weekly((Day.THURSDAY,), "09:00", "13:00")
        + weekly((Day.TUESDAY, Day.THURSDAY), "15:00", "18:00"),
    ),
)
