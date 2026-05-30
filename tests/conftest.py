import os
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from tests.factories import DoctorFactory, PatientFactory, UserFactory

# ---------------------------------------------------------------------------
# Load .env.test BEFORE Django settings are evaluated.
# pytest_configure runs earlier than module-level code in conftest.py,
# so DATABASE_URL is available when dj_database_url.config() is called.
# ---------------------------------------------------------------------------
def _load_env_file(path: Path) -> None:
    """Parse a .env file and set variables via os.environ.setdefault."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def pytest_configure(config):
    """Load .env.test before Django initialises its settings."""
    _load_env_file(Path(__file__).resolve().parent.parent / ".env.test")


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
