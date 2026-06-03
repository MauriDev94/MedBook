"""Integration tests for CORS headers.

Verifies that django-cors-headers is wired correctly: allowed origins receive
the Access-Control-Allow-Origin header and preflight OPTIONS requests succeed.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestCORSHeaders:
    def test_allowed_origin_receives_cors_header(self, settings):
        """Requests from an allowed origin must include the CORS header."""
        settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

        client = APIClient()
        response = client.get(
            "/api/doctors/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        assert "Access-Control-Allow-Origin" in response

    def test_disallowed_origin_does_not_receive_cors_header(self, settings):
        """Requests from unknown origins must NOT include the CORS header."""
        settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

        client = APIClient()
        response = client.get(
            "/api/doctors/",
            HTTP_ORIGIN="http://evil.com",
        )
        assert "Access-Control-Allow-Origin" not in response

    def test_preflight_options_returns_200(self, settings):
        """OPTIONS preflight from an allowed origin must return 200."""
        settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

        client = APIClient()
        response = client.options(
            "/api/doctors/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert response.status_code == status.HTTP_200_OK
