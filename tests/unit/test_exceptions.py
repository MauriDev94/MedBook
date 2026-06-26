"""Unit tests for custom_exception_handler.

Verifies that every DRF exception type is normalised to the same shape:
    {
        "detail": "<human-readable message>",
        "code":   "<machine-readable code>",
        "field_errors": { ... }   # only present for validation errors
    }
"""

import pytest
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.core.exceptions import custom_exception_handler


def call_handler(exc):
    """Call the handler with a minimal context."""
    return custom_exception_handler(exc, context={})


@pytest.mark.django_db
class TestExceptionHandlerShape:
    def test_not_found_returns_standard_shape(self):
        response = call_handler(NotFound())

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == "not_found"
        assert "detail" in response.data
        assert "field_errors" not in response.data

    def test_permission_denied_returns_standard_shape(self):
        response = call_handler(PermissionDenied())

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == "permission_denied"
        assert "detail" in response.data
        assert "field_errors" not in response.data

    def test_not_authenticated_returns_standard_shape(self):
        response = call_handler(NotAuthenticated())

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["code"] == "not_authenticated"
        assert "detail" in response.data

    def test_authentication_failed_returns_standard_shape(self):
        response = call_handler(AuthenticationFailed())

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["code"] == "authentication_failed"
        assert "detail" in response.data

    def test_validation_error_with_field_errors(self):
        exc = ValidationError(
            {"email": ["This field is required."], "slot": ["Invalid slot."]}
        )
        response = call_handler(exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert "field_errors" in response.data
        assert "email" in response.data["field_errors"]
        assert "slot" in response.data["field_errors"]

    def test_validation_error_with_non_field_errors(self):
        exc = ValidationError({"non_field_errors": ["Overlapping appointment exists."]})
        response = call_handler(exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert response.data["detail"] == "Overlapping appointment exists."
        assert "field_errors" not in response.data

    def test_validation_error_with_plain_string(self):
        exc = ValidationError("This slot is no longer available.")
        response = call_handler(exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert "detail" in response.data

    def test_validation_error_with_single_detail_key(self):
        """A ValidationError carrying a lone {'detail': ...} → detail passthrough."""
        exc = ValidationError({"detail": "Single detail message."})
        response = call_handler(exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert response.data["detail"] == "Single detail message."
        assert "field_errors" not in response.data

    def test_non_drf_exception_returns_none(self):
        response = call_handler(ValueError("something broke"))

        assert response is None

    def test_django_validation_error_maps_to_400(self):
        """Django's ValidationError (raised by services) → 400, not a 500.

        Services raise django.core.exceptions.ValidationError. When this
        escapes outside DRF's run_validation (e.g. from a service called in
        serializer.create()), DRF's default handler returns None → Django 500.
        The custom handler must catch it and normalise it to a 400.
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        exc = DjangoValidationError("This time slot is no longer available.")
        response = call_handler(exc)

        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert response.data["detail"] == "This time slot is no longer available."

    def test_django_validation_error_with_message_list(self):
        """Django ValidationError carrying multiple messages → first as detail."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        exc = DjangoValidationError(["First problem.", "Second problem."])
        response = call_handler(exc)

        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "validation_error"
        assert response.data["detail"] == "First problem."


@pytest.mark.django_db
class TestExceptionHandlerIntegration:
    """Hit real endpoints to verify the shape end-to-end."""

    def test_unauthenticated_request_returns_standard_shape(self, api_client):
        response = api_client.get("/api/v1/users/me/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "code" in response.data
        assert "detail" in response.data

    def test_invalid_token_returns_standard_shape(self, api_client):
        response = api_client.post(
            "/api/v1/token/",
            {"email": "noexiste@example.com", "password": "wrong"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "code" in response.data
        assert "detail" in response.data

    def test_not_found_returns_standard_shape(self, api_client):
        from tests.factories import UserFactory

        user = UserFactory()
        api_client.force_authenticate(user=user)

        response = api_client.get(
            "/api/v1/appointments/00000000-0000-0000-0000-000000000000/"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "code" in response.data
        assert "detail" in response.data
