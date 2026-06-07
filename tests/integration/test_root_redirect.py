"""Root URL redirect tests.

Verifies that GET / redirects to the Swagger docs at /api/docs/.
The deployment base URL is shared publicly (CV/recruiters), so the root
must land on the interactive documentation instead of a 404.
No authentication required — this is a public entry point.
"""


class TestRootRedirect:
    url = "/"

    def test_redirects_to_api_docs(self, client):
        response = client.get(self.url)

        assert response.status_code == 302
        assert response["Location"] == "/api/docs/"

    def test_redirect_is_temporary(self, client):
        """A 302 (not 301) keeps the target swappable without browser caching."""
        response = client.get(self.url)

        assert response.status_code == 302

    def test_no_authentication_required(self, client):
        """Root entry point must be publicly accessible — no JWT needed."""
        response = client.get(self.url)

        assert response.status_code == 302
