import jwt
from rest_framework import status

from tests.factories import UserFactory


class TestAuthAPI:
    """Test JWT authentication endpoints."""

    def test_token_obtain_success(self, api_client, db):
        """Test POST /api/token/ returns 200 with access and refresh tokens."""
        UserFactory(email="test@example.com", password="testpass123")

        response = api_client.post(
            "/api/v1/token/",
            {"email": "test@example.com", "password": "testpass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_token_contains_custom_claims(self, api_client, db):
        """Test the decoded token contains role, email and full_name."""
        UserFactory(
            email="doctor@example.com",
            password="testpass123",
            role="doctor",
            first_name="Jane",
            last_name="Smith",
        )

        response = api_client.post(
            "/api/v1/token/",
            {"email": "doctor@example.com", "password": "testpass123"},
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
            {"email": "test@example.com", "password": "wrongpassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, db):
        """Test POST /api/token/refresh/ returns a new access token."""
        UserFactory(email="test@example.com", password="testpass123")

        token_response = api_client.post(
            "/api/v1/token/",
            {"email": "test@example.com", "password": "testpass123"},
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
