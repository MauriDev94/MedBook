"""Integration tests for UserViewSet and auth endpoints.

Covers:
- GET /api/users/me/       → profile of the authenticated user
- PATCH /api/users/me/     → update first_name / last_name
- POST /api/token/blacklist/ → logout (refresh token invalidated)
"""

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import UserFactory


@pytest.mark.django_db
class TestUserMeEndpoint:
    """GET /api/users/me/ — read authenticated user's profile."""

    def test_me_returns_profile(self, api_client):
        user = UserFactory(
            email="patient@example.com",
            first_name="Ana",
            last_name="García",
            role="patient",
        )
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/v1/users/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "patient@example.com"
        assert response.data["full_name"] == "Ana García"
        assert response.data["role"] == "patient"

    def test_me_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/users/me/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_response_has_expected_fields(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/v1/users/me/")

        assert response.status_code == status.HTTP_200_OK
        for field in [
            "id",
            "email",
            "role",
            "full_name",
            "first_name",
            "last_name",
            "created_at",
        ]:
            assert field in response.data, f"Missing field: {field}"

    def test_me_does_not_expose_password(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/v1/users/me/")

        assert "password" not in response.data


@pytest.mark.django_db
class TestUserMePatchEndpoint:
    """PATCH /api/users/me/ — update editable profile fields."""

    def test_patch_updates_first_and_last_name(self, api_client):
        user = UserFactory(first_name="Old", last_name="Name")
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            "/api/v1/users/me/",
            {"first_name": "New", "last_name": "Name"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "New"
        assert response.data["full_name"] == "New Name"

        user.refresh_from_db()
        assert user.first_name == "New"

    def test_patch_cannot_change_email(self, api_client):
        user = UserFactory(email="original@example.com")
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            "/api/v1/users/me/",
            {"email": "hacked@example.com"},
            format="json",
        )

        # Either 200 with email unchanged, or ignored silently
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.email == "original@example.com"

    def test_patch_cannot_change_role(self, api_client):
        user = UserFactory(role="patient")
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            "/api/v1/users/me/",
            {"role": "admin"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.role == "patient"

    def test_patch_partial_update_only_first_name(self, api_client):
        user = UserFactory(first_name="Ana", last_name="García")
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            "/api/v1/users/me/",
            {"first_name": "María"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "María"
        assert response.data["last_name"] == "García"

    def test_patch_response_returns_full_profile(self, api_client):
        """PATCH must echo the FULL profile, not just the edited fields.

        Pins the behaviour after the DRY refactor: the write serializer only
        accepts first_name/last_name, but the view re-serializes with the read
        serializer so the response still carries id, email, role, created_at.
        """
        user = UserFactory(
            email="full@example.com", role="patient", first_name="A", last_name="B"
        )
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            "/api/v1/users/me/",
            {"first_name": "Updated"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        for field in ["id", "email", "role", "full_name", "created_at"]:
            assert field in response.data, f"Missing field in PATCH response: {field}"
        assert response.data["email"] == "full@example.com"
        assert response.data["full_name"] == "Updated B"

    def test_patch_unauthenticated_returns_401(self, api_client):
        response = api_client.patch(
            "/api/v1/users/me/",
            {"first_name": "Ana"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogoutEndpoint:
    """POST /api/token/blacklist/ — logout by blacklisting the refresh token."""

    def test_logout_returns_200(self, api_client):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)

        response = api_client.post(
            "/api/v1/token/blacklist/",
            {"refresh": str(refresh)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_logout_blacklisted_token_cannot_be_refreshed(self, api_client):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        refresh_str = str(refresh)

        # Blacklist
        api_client.post(
            "/api/v1/token/blacklist/",
            {"refresh": refresh_str},
            format="json",
        )

        # Attempt to use the same refresh token
        response = api_client.post(
            "/api/v1/token/refresh/",
            {"refresh": refresh_str},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_missing_refresh_token_returns_400(self, api_client):
        response = api_client.post(
            "/api/v1/token/blacklist/",
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
