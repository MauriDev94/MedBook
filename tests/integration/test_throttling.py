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


@pytest.mark.django_db
class TestGlobalAnonRateThrottle:
    """Global throttling must apply to anonymous requests on any endpoint."""

    def test_anon_requests_are_throttled_globally(self, monkeypatch):
        """Unauthenticated requests must be globally rate limited.

        Every protected endpoint requires IsAuthenticated, and DRF checks
        permissions before throttles (see APIView.initial()), so anonymous
        requests to those endpoints always 401 before the throttle can ever
        fire. The token-obtain endpoint is the only AllowAny endpoint, so we
        use it here — but with a rate far looser than LoginRateThrottle's,
        so the 429 we observe is caused by the global AnonRateThrottle, not
        by the login-specific one.
        """
        from rest_framework.throttling import AnonRateThrottle

        from apps.core.throttling import LoginRateThrottle

        monkeypatch.setattr(AnonRateThrottle, "get_rate", lambda self: "3/minute")
        monkeypatch.setattr(LoginRateThrottle, "get_rate", lambda self: "1000/minute")

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


@pytest.mark.django_db
class TestGlobalUserRateThrottle:
    """Global throttling must apply to authenticated requests on any endpoint."""

    def test_authenticated_requests_are_throttled_globally(
        self, monkeypatch, user_patient
    ):
        """Authenticated requests must be globally rate limited."""
        from rest_framework.throttling import UserRateThrottle

        monkeypatch.setattr(UserRateThrottle, "get_rate", lambda self: "3/minute")

        client = APIClient()
        client.force_authenticate(user=user_patient)
        for _ in range(3):
            client.get("/api/doctors/")

        response = client.get("/api/doctors/")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestRefreshRateThrottle:
    """The token refresh endpoint must have its own throttle scope."""

    def test_refresh_rate_limit_returns_429(self, monkeypatch):
        """Exceeding the refresh rate limit must return 429 Too Many Requests."""
        from apps.core.throttling import RefreshRateThrottle

        monkeypatch.setattr(RefreshRateThrottle, "get_rate", lambda self: "3/minute")

        client = APIClient()
        for _ in range(4):
            response = client.post(
                "/api/token/refresh/",
                {"refresh": "invalid-token"},
                format="json",
            )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_refresh_under_limit_returns_normal_status(self):
        """A single refresh request under the limit must not be throttled."""
        client = APIClient()
        response = client.post(
            "/api/token/refresh/",
            {"refresh": "invalid-token"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRefreshTokenRotation:
    """SIMPLE_JWT ROTATE_REFRESH_TOKENS must invalidate the old refresh token."""

    def test_old_refresh_token_is_blacklisted_after_rotation(self, user_patient):
        """After refreshing, the old refresh token must be rejected (blacklisted)."""
        from rest_framework_simplejwt.tokens import RefreshToken

        old_refresh = RefreshToken.for_user(user_patient)

        client = APIClient()
        first_response = client.post(
            "/api/token/refresh/",
            {"refresh": str(old_refresh)},
            format="json",
        )
        assert first_response.status_code == status.HTTP_200_OK
        assert "refresh" in first_response.data  # rotation issues a new refresh

        # Re-using the old (now rotated) refresh token must fail.
        second_response = client.post(
            "/api/token/refresh/",
            {"refresh": str(old_refresh)},
            format="json",
        )
        assert second_response.status_code == status.HTTP_401_UNAUTHORIZED
