"""Core views — infrastructure endpoints not tied to a domain model."""

from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """GET /health/ — reports DB connectivity.

    Returns 200 when the database is reachable, 503 otherwise.
    No authentication required — consumed by Render health checks and monitoring.
    """
    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok", "database": "ok"})
    except Exception:
        return JsonResponse(
            {"status": "error", "database": "error"},
            status=503,
        )
