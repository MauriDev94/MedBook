import jwt
import pytest
from django.core.cache import cache
from rest_framework import status

from tests.factories import UserFactory, random_password


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """The token endpoint allows 5 logins a minute per IP ("login" scope)."""
    cache.clear()
    yield
    cache.clear()


class TestAuthAPI:
    """Test JWT authentication endpoints."""

    def test_token_obtain_success(self, api_client, db):
        """Test POST /api/token/ returns 200 with access and refresh tokens."""
        user = UserFactory(email="test@example.com")

        response = api_client.post(
            "/api/v1/token/",
            {"email": user.email, "password": user.raw_password},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_token_contains_custom_claims(self, api_client, db):
        """Test the decoded token contains role, email and full_name."""
        user = UserFactory(
            email="doctor@example.com",
            role="doctor",
            first_name="Jane",
            last_name="Smith",
        )

        response = api_client.post(
            "/api/v1/token/",
            {"email": user.email, "password": user.raw_password},
            format="json",
        )

        token = response.data["access"]
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["role"] == "doctor"
        assert payload["email"] == "doctor@example.com"
        assert payload["full_name"] == "Jane Smith"

    def test_token_obtain_invalid_credentials(self, api_client, db):
        """Test POST /api/token/ with wrong password returns 401."""
        UserFactory(email="test@example.com")

        response = api_client.post(
            "/api/v1/token/",
            {"email": "test@example.com", "password": random_password()},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_obtain_ignores_email_case(self, api_client, db):
        """An account registered as ana@… logs in as ANA@… (Paso 34)."""
        user = UserFactory(email="ana@example.com")

        response = api_client.post(
            "/api/v1/token/",
            {"email": "ANA@Example.com", "password": user.raw_password},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_wrong_password_and_unknown_email_get_the_same_error(self, api_client, db):
        """The 401 must not reveal whether the email is registered."""
        UserFactory(email="ana@example.com")

        wrong_password = api_client.post(
            "/api/v1/token/",
            {"email": "ANA@example.com", "password": random_password()},
            format="json",
        )
        unknown_email = api_client.post(
            "/api/v1/token/",
            {"email": "nadie@example.com", "password": random_password()},
            format="json",
        )

        assert wrong_password.status_code == status.HTTP_401_UNAUTHORIZED
        assert wrong_password.data == unknown_email.data

    def test_token_refresh(self, api_client, db):
        """Test POST /api/token/refresh/ returns a new access token."""
        user = UserFactory(email="test@example.com")

        token_response = api_client.post(
            "/api/v1/token/",
            {"email": user.email, "password": user.raw_password},
            format="json",
        )
        refresh_token = token_response.data["refresh"]

        response = api_client.post(
            "/api/v1/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
