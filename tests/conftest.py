import pytest
from rest_framework.test import APIClient

from tests.factories import DoctorFactory, PatientFactory, UserFactory


@pytest.fixture(autouse=True)
def timezone_settings(settings):
    """Ensure consistent timezone across all tests."""
    settings.TIME_ZONE = "UTC"


@pytest.fixture
def api_client():
    """Return DRF API client."""
    return APIClient()


@pytest.fixture
def user_patient(db):
    """Create a test patient user."""
    return UserFactory(role="patient")


@pytest.fixture
def user_doctor(db):
    """Create a test doctor user with a Doctor profile."""
    return UserFactory(role="doctor")


@pytest.fixture
def user_admin(db):
    """Create a test admin user."""
    return UserFactory(role="admin", is_staff=True)


@pytest.fixture
def doctor_profile(db, user_doctor):
    """Create a Doctor profile for user_doctor."""
    return DoctorFactory(user=user_doctor)


@pytest.fixture
def patient_profile(db, user_patient):
    """Create a Patient profile for user_patient."""
    return PatientFactory(user=user_patient)
