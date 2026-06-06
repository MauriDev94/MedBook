"""Health check endpoint tests.

Verifies that GET /health/ reports DB connectivity correctly.
No authentication required — this is an infrastructure endpoint.
"""

from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestHealthEndpoint:
    url = "/health/"

    def test_returns_200_and_ok_when_db_healthy(self, client):
        response = client.get(self.url)

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}

    def test_returns_503_and_error_when_db_down(self, client):
        with patch("apps.core.views.connection.ensure_connection") as mock_conn:
            mock_conn.side_effect = Exception("Connection refused")
            response = client.get(self.url)

        assert response.status_code == 503
        assert response.json() == {"status": "error", "database": "error"}

    def test_no_authentication_required(self, client):
        """Health check must be publicly accessible — no JWT needed."""
        # client has no auth headers set
        response = client.get(self.url)

        assert response.status_code == 200
