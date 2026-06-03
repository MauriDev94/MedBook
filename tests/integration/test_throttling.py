"""Integration tests for rate limiting on auth endpoints.

DRF throttling uses Django's cache backend to track request counts.
The cache must be cleared between tests to avoid state leakage.

Throttle rates are overridden per test via monkeypatch so the suite
runs fast (no real 60-second windows needed).
"""

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Clear DRF throttle cache before and after every test in this module."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLoginRateThrottle:
    def test_login_under_limit_returns_normal_status(self):
        """Requests under the limit should not be throttled."""
        client = APIClient()
        # A single bad-credential request should return 401, not 429
        response = client.post(
            "/api/token/",
            {"email": "nobody@test.com", "password": "wrong"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_rate_limit_returns_429(self, monkeypatch):
        """Exceeding the rate limit must return 429 Too Many Requests."""
        from apps.core.throttling import LoginRateThrottle

        # Override to 3/minute so the test doesn't need to make 5 real requests
        monkeypatch.setattr(LoginRateThrottle, "get_rate", lambda self: "3/minute")

        client = APIClient()
        for _ in range(3):
            client.post(
                "/api/token/",
                {"email": "nobody@test.com", "password": "wrong"},
                format="json",
            )

        response = client.post(
            "/api/token/",
            {"email": "nobody@test.com", "password": "wrong"},
            format="json",
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_429_response_includes_retry_after_header(self, monkeypatch):
        """Throttled responses must include the Retry-After header."""
        from apps.core.throttling import LoginRateThrottle

        monkeypatch.setattr(LoginRateThrottle, "get_rate", lambda self: "3/minute")

        client = APIClient()
        for _ in range(3):
            client.post(
                "/api/token/",
                {"email": "nobody@test.com", "password": "wrong"},
                format="json",
            )

        response = client.post(
            "/api/token/",
            {"email": "nobody@test.com", "password": "wrong"},
            format="json",
        )
        assert "Retry-After" in response

    def test_throttle_only_applies_to_token_endpoint(self, monkeypatch):
        """Other endpoints must NOT be throttled by LoginRateThrottle."""
        from apps.core.throttling import LoginRateThrottle

        monkeypatch.setattr(LoginRateThrottle, "get_rate", lambda self: "3/minute")

        client = APIClient()
        # Exhaust the login throttle
        for _ in range(4):
            client.post(
                "/api/token/",
                {"email": "nobody@test.com", "password": "wrong"},
                format="json",
            )

        # Doctors list should still be accessible (different throttle scope)
        response = client.get("/api/doctors/")
        # 401 (auth required) not 429 (throttled)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
