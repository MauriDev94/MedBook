import factory
from django.contrib.auth import get_user_model

from apps.doctors.models import Doctor, Specialty
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
