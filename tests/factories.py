import datetime
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.appointments.models import Appointment, MedicalNote, TimeSlot
from apps.doctors.models import Doctor, Schedule, Specialty
from apps.patients.models import Patient
from apps.users.models import Role

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    role = Role.PATIENT
    is_active = True


class SpecialtyFactory(factory.django.DjangoModelFactory):
    """Factory for Specialty model."""

    class Meta:
        model = Specialty
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Specialty {n}")
    slug = factory.Sequence(lambda n: f"specialty-{n}")


class DoctorFactory(factory.django.DjangoModelFactory):
    """Factory for Doctor model."""

    class Meta:
        model = Doctor

    user = factory.SubFactory(UserFactory, role=Role.DOCTOR)
    license_number = factory.Sequence(lambda n: f"LIC-{n:04d}")
    consultation_duration = 30

    @factory.post_generation
    def specialties(self, create, extracted, **kwargs):
        """Add specialties to doctor."""
        if not create:
            return
        if extracted:
            for specialty in extracted:
                self.specialties.add(specialty)


class PatientFactory(factory.django.DjangoModelFactory):
    """Factory for Patient model."""

    class Meta:
        model = Patient

    user = factory.SubFactory(UserFactory, role=Role.PATIENT)
    date_of_birth = factory.Faker("date_of_birth")
    phone = factory.Sequence(lambda n: f"+5691{n:07d}")


class ScheduleFactory(factory.django.DjangoModelFactory):
    """Factory for Schedule model."""

    class Meta:
        model = Schedule

    doctor = factory.SubFactory(DoctorFactory)
    day_of_week = 0  # Monday
    start_time = datetime.time(9, 0)
    end_time = datetime.time(17, 0)
    is_active = True


class TimeSlotFactory(factory.django.DjangoModelFactory):
    """Factory for TimeSlot model."""

    class Meta:
        model = TimeSlot

    schedule = factory.SubFactory(ScheduleFactory)
    start_datetime = factory.LazyAttribute(lambda o: timezone.now() + timedelta(days=1))
    end_datetime = factory.LazyAttribute(
        lambda o: (
            o.start_datetime
            + timedelta(minutes=o.schedule.doctor.consultation_duration)
        )
    )
    status = TimeSlot.Status.AVAILABLE


class AppointmentFactory(factory.django.DjangoModelFactory):
    """Factory for Appointment model.

    Note: The `slot` factory creates its own Schedule and Doctor.
    For tests where the appointment doctor must match the slot's doctor,
    pass the slot explicitly or use traits.
    """

    class Meta:
        model = Appointment

    patient = factory.SubFactory(PatientFactory)
    doctor = factory.SubFactory(DoctorFactory)
    slot = factory.SubFactory(TimeSlotFactory)
    reason = factory.Faker("text", max_nb_chars=200)
    status = Appointment.Status.PENDING


class MedicalNoteFactory(factory.django.DjangoModelFactory):
    """Factory for MedicalNote model."""

    class Meta:
        model = MedicalNote

    appointment = factory.SubFactory(AppointmentFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("paragraph")
