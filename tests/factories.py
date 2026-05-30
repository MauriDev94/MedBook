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
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    role = Role.PATIENT
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Hash and persist the password explicitly.

        skip_postgeneration_save=True skips the automatic save after all
        post-generation hooks, so we must call save() ourselves here to
        ensure the hashed password is written to the DB.
        """
        if not create:
            return
        self.set_password(extracted or "testpass123")
        self.save(update_fields=["password"])


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
        skip_postgeneration_save = True

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
    day_of_week = Schedule.DayOfWeek.MONDAY
    start_time = factory.Faker("time_object")
    end_time = factory.LazyAttribute(
        lambda o: (
            timezone.datetime.combine(timezone.datetime.today(), o.start_time)
            + timezone.timedelta(hours=8)
        ).time()
    )
    is_active = True


class TimeSlotFactory(factory.django.DjangoModelFactory):
    """Factory for TimeSlot model."""

    class Meta:
        model = TimeSlot

    schedule = factory.SubFactory(ScheduleFactory)
    start_datetime = factory.LazyFunction(
        lambda: timezone.now().replace(minute=0, second=0, microsecond=0)
        + timezone.timedelta(days=1)
    )
    end_datetime = factory.LazyAttribute(
        lambda o: o.start_datetime + timezone.timedelta(minutes=30)
    )
    status = TimeSlot.Status.AVAILABLE


class AppointmentFactory(factory.django.DjangoModelFactory):
    """Factory for Appointment model."""

    class Meta:
        model = Appointment

    patient = factory.SubFactory(PatientFactory)
    doctor = factory.SubFactory(DoctorFactory)
    slot = factory.SubFactory(TimeSlotFactory)
    reason = factory.Faker("sentence")
    status = Appointment.Status.PENDING


class MedicalNoteFactory(factory.django.DjangoModelFactory):
    """Factory for MedicalNote model."""

    class Meta:
        model = MedicalNote

    appointment = factory.SubFactory(AppointmentFactory)
    author = factory.LazyAttribute(lambda o: o.appointment.doctor.user)
    content = factory.Faker("paragraph")
