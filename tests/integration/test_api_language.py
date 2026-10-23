"""The JSON API stays in English (Paso 24, ADR 0002).

The web UI is translated, but API error messages are part of a stable
contract: they must not change with Accept-Language or the web's language
cookie.
"""

import pytest
from django.conf import settings
from django.core.cache import cache

from tests.factories import random_password

ME_URL = "/api/v1/users/me/"
REGISTER_URL = "/api/v1/users/register/"
NOT_AUTHENTICATED = "Authentication credentials were not provided."
REQUIRED = "This field is required."


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Registration and anonymous requests are throttled per IP."""
    cache.clear()


@pytest.mark.django_db
class TestApiStaysInEnglish:
    def test_auth_error_ignores_spanish_accept_language(self, api_client):
        response = api_client.get(ME_URL, headers={"Accept-Language": "es"})

        assert response.status_code == 401
        assert response.json()["detail"] == NOT_AUTHENTICATED

    def test_validation_errors_ignore_spanish_accept_language(self, api_client):
        response = api_client.post(
            REGISTER_URL, {}, format="json", headers={"Accept-Language": "es"}
        )

        assert response.status_code == 400
        assert response.json()["field_errors"]["email"] == [REQUIRED]

    def test_duplicate_email_error_ignores_spanish_accept_language(
        self, api_client, user_patient
    ):
        """The service message is translatable for the web, never for the API."""
        response = api_client.post(
            REGISTER_URL,
            {
                "email": user_patient.email,
                "password": random_password(),
                "first_name": "Ana",
                "last_name": "Rojas",
            },
            format="json",
            headers={"Accept-Language": "es"},
        )

        assert response.status_code == 400
        assert response.json()["field_errors"]["email"] == [
            "A user with this email already exists."
        ]

    def test_api_ignores_web_language_cookie(self, api_client):
        api_client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"

        response = api_client.get(ME_URL)

        assert response.json()["detail"] == NOT_AUTHENTICATED

    def test_api_declares_english_content_language(self, api_client):
        response = api_client.get(ME_URL, headers={"Accept-Language": "es"})

        assert response["Content-Language"] == "en"
