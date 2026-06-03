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
