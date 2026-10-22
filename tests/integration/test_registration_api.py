"""Integration tests for POST /api/v1/users/register/ (patient self-sign-up).

Contract:
- Public endpoint (no auth); always creates a patient — `role` in the payload
  is ignored.
- 201 returns the profile only (UserSerializer shape), never tokens: the
  client logs in afterwards through /api/v1/token/.
- Validation errors use the standard {detail, code, field_errors} shape.
- Rate limited per IP with its own "register" throttle scope.
"""

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.patients.models import Patient
from apps.users.models import Role, User
from tests.factories import UserFactory

URL = "/api/v1/users/register/"

# A phrase that passes every AUTH_PASSWORD_VALIDATORS check.
REGISTRATION_PHRASE = "medbook-registro-2026"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Registration is throttled per IP; keep counts isolated per test."""
    cache.clear()
    yield
    cache.clear()


def _payload(**overrides):
    data = {
        "email": "ana.perez@example.com",
        "password": REGISTRATION_PHRASE,
        "first_name": "Ana",
        "last_name": "Pérez",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestRegisterSuccess:
    def test_returns_201_with_profile(self, api_client):
        response = api_client.post(URL, _payload(), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "ana.perez@example.com"
        assert response.data["role"] == Role.PATIENT
        assert response.data["full_name"] == "Ana Pérez"
        assert set(response.data) == {
            "id",
            "email",
            "role",
            "full_name",
            "first_name",
            "last_name",
            "created_at",
        }

    def test_response_has_no_tokens_or_password(self, api_client):
        response = api_client.post(URL, _payload(), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        for field in ("access", "refresh", "password"):
            assert field not in response.data

    def test_creates_patient_profile_with_optional_fields(self, api_client):
        response = api_client.post(
            URL,
            _payload(
                phone="+56912345678",
                date_of_birth="1990-05-17",
                emergency_contact="Juan Pérez +56987654321",
            ),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        profile = Patient.objects.get(user__email="ana.perez@example.com")
        assert profile.phone == "+56912345678"
        assert str(profile.date_of_birth) == "1990-05-17"
        assert profile.emergency_contact == "Juan Pérez +56987654321"

    def test_role_in_payload_is_ignored(self, api_client):
        response = api_client.post(
            URL, _payload(role=Role.ADMIN, is_staff=True), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="ana.perez@example.com")
        assert user.role == Role.PATIENT
        assert user.is_staff is False

    def test_new_user_can_log_in(self, api_client):
        api_client.post(URL, _payload(), format="json")

        response = api_client.post(
            "/api/v1/token/",
            {"email": "ana.perez@example.com", "password": REGISTRATION_PHRASE},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_invalid_bearer_token_does_not_block_registration(self):
        """The endpoint is public: a stale Authorization header must not 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

        response = client.post(URL, _payload(), format="json")

        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestRegisterValidation:
    def test_duplicate_email_returns_400_with_field_error(self, api_client):
        UserFactory(email="ana.perez@example.com")

        response = api_client.post(URL, _payload(), format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert "email" in response.data["field_errors"]

    def test_weak_password_returns_400_with_field_error(self, api_client):
        response = api_client.post(URL, _payload(password="12345"), format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data["field_errors"]

    def test_missing_required_fields_return_field_errors(self, api_client):
        response = api_client.post(URL, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert set(response.data["field_errors"]) == {
            "email",
            "password",
            "first_name",
            "last_name",
        }

    def test_invalid_email_format_returns_400(self, api_client):
        response = api_client.post(URL, _payload(email="not-an-email"), format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data["field_errors"]

    def test_failed_registration_creates_nothing(self, api_client):
        api_client.post(URL, _payload(password="12345"), format="json")

        assert not User.objects.exists()
        assert not Patient.objects.exists()


@pytest.mark.django_db
class TestRegisterThrottle:
    def test_exceeding_register_rate_returns_429(self, monkeypatch):
        from apps.core.throttling import RegisterRateThrottle

        monkeypatch.setattr(RegisterRateThrottle, "get_rate", lambda self: "2/minute")

        client = APIClient()
        for n in range(2):
            client.post(URL, _payload(email=f"user{n}@example.com"), format="json")

        response = client.post(URL, _payload(email="user9@example.com"), format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
