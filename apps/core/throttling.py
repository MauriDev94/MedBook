"""Custom DRF throttle classes for MedBook.

Uses DRF's built-in SimpleRateThrottle mechanism — no extra packages required.
Rates are configured in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].
"""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Rate limit for the JWT token obtain endpoint (/api/token/).

    Limits unauthenticated login attempts to prevent brute-force attacks.
    Rate configured via settings: DEFAULT_THROTTLE_RATES["login"].

    Default: 5 requests per minute per IP.
    """

    scope = "login"


class RefreshRateThrottle(AnonRateThrottle):
    """Rate limit for the JWT token refresh endpoint (/api/token/refresh/).

    Refresh requests are unauthenticated (the access token may already be
    expired), so this is IP-based like LoginRateThrottle. Prevents abuse of
    the refresh flow (e.g. brute-forcing stolen/expired refresh tokens).
    Rate configured via settings: DEFAULT_THROTTLE_RATES["refresh"].

    Default: 10 requests per minute per IP.
    """

    scope = "refresh"
