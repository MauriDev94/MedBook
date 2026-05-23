import pytest
from django.contrib.auth import get_user_model

from apps.doctors.models import Doctor, Specialty
from apps.patients.models import Patient
from apps.users.models import Role
from tests.factories import (
    DoctorFactory,
    PatientFactory,
    SpecialtyFactory,
    UserFactory,
)

User = get_user_model()


class TestUserModel:
    """Test User model."""

    def test_create_user_with_email(self, db):
        """Test creating a regular user with email."""
        user = UserFactory(email="test@example.com")
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_default_role_is_patient(self, db):
        """Test default role is patient."""
        user = UserFactory()
        assert user.role == Role.PATIENT

    def test_full_name_with_first_and_last(self, db):
        """Test full_name property combines names."""
        user = UserFactory(first_name="John", last_name="Doe")
        assert user.full_name == "John Doe"

    def test_full_name_without_names(self, db):
        """Test full_name returns empty string when no names set."""
        user = UserFactory(first_name="", last_name="")
        assert user.full_name == ""

    def test_user_str_returns_email(self, db):
        """Test __str__ returns email."""
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_create_superuser(self, db):
        """Test creating a superuser."""
        admin = UserFactory(
            is_staff=True,
            is_superuser=True,
            role=Role.ADMIN,
        )
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.role == Role.ADMIN


class TestDoctorModel:
    """Test Doctor model."""

    def test_create_doctor(self, db):
        """Test creating a doctor with factory."""
        doctor = DoctorFactory()
        assert doctor.id is not None
        assert doctor.user.role == Role.DOCTOR
        assert doctor.consultation_duration == 30

    def test_doctor_str(self, db):
        """Test __str__ returns formatted name."""
        doctor = DoctorFactory()
        user = doctor.user
        expected = f"Dr. {user.full_name}"
        assert str(doctor) == expected

    def test_doctor_with_specialties(self, db):
        """Test doctor can have multiple specialties."""
        specialties = SpecialtyFactory.create_batch(3)
        doctor = DoctorFactory(specialties=specialties)
        assert doctor.specialties.count() == 3


class TestPatientModel:
    """Test Patient model."""

    def test_create_patient(self, db):
        """Test creating a patient with factory."""
        patient = PatientFactory()
        assert patient.id is not None
        assert patient.user.role == Role.PATIENT

    def test_patient_str(self, db):
        """Test __str__ returns user full name or email."""
        patient = PatientFactory()
        expected = patient.user.full_name or patient.user.email
        assert str(patient) == expected

    def test_patient_phone_optional(self, db):
        """Test phone field is optional."""
        patient = PatientFactory(phone="")
        assert patient.phone == ""


class TestSpecialtyModel:
    """Test Specialty model."""

    def test_create_specialty(self, db):
        """Test creating a specialty."""
        specialty = SpecialtyFactory(name="Cardiology", slug="cardiology")
        assert specialty.name == "Cardiology"
        assert specialty.slug == "cardiology"

    def test_specialty_str(self, db):
        """Test __str__ returns name."""
        specialty = SpecialtyFactory(name="Dermatology")
        assert str(specialty) == "Dermatology"

    def test_specialty_slug_unique(self, db):
        """Test slug must be unique."""
        SpecialtyFactory(slug="unique-slug")
        with pytest.raises(Exception):
            SpecialtyFactory(slug="unique-slug")
