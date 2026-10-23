"""Web home page tests (Paso 24, ADR 0002).

`/` serves the server-rendered home instead of redirecting to Swagger; the
API docs stay at /api/docs/. The layout loads the compiled Tailwind CSS and
the vendored HTMX, and every HTMX request carries the CSRF token.
"""

from django.contrib.staticfiles import finders
from pytest_django.asserts import assertTemplateUsed

HTMX_STATIC_PATH = "vendor/htmx-2.0.11.min.js"


class TestHomePage:
    url = "/"

    def test_home_renders_with_base_layout(self, client):
        response = client.get(self.url)

        assert response.status_code == 200
        assertTemplateUsed(response, "web/home.html")
        assertTemplateUsed(response, "web/base.html")

    def test_no_authentication_required(self, client):
        """The home is the public entry point shared on the CV."""
        response = client.get(self.url)

        assert response.status_code == 200
        assert not response.wsgi_request.user.is_authenticated

    def test_api_docs_still_served(self, client):
        response = client.get("/api/docs/")

        assert response.status_code == 200

    def test_layout_links_tailwind_css(self, client):
        response = client.get(self.url)

        assert "/static/css/tailwind.css" in response.content.decode()


class TestHtmx:
    url = "/"

    def test_htmx_is_vendored_with_a_pinned_version(self, client):
        response = client.get(self.url)

        assert f"/static/{HTMX_STATIC_PATH}" in response.content.decode()
        assert finders.find(HTMX_STATIC_PATH) is not None

    def test_htmx_requests_carry_csrf_token(self, client):
        response = client.get(self.url)

        token = str(response.context["csrf_token"])
        assert f'hx-headers=\'{{"X-CSRFToken": "{token}"}}\'' in (
            response.content.decode()
        )
        assert "csrftoken" in response.cookies

    def test_request_htmx_is_set_for_htmx_requests(self, client):
        response = client.get(self.url, headers={"HX-Request": "true"})

        assert response.wsgi_request.htmx

    def test_request_htmx_is_falsy_for_plain_requests(self, client):
        response = client.get(self.url)

        assert not response.wsgi_request.htmx
