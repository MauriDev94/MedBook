"""Error pages: 403, 404 and 500 with the web layout (Paso 29).

Django renders the root 403.html and 404.html with the request, so they
keep the visitor's menu and language. The 500 page is rendered with no
context at all and must not touch the database (it may be what failed):
these tests run without database access, so any query would fail them.
DEBUG is False here, as in production; with DEBUG Django shows its
debug pages instead.
"""

import pytest
from django.test import Client
from django.urls import path
from pytest_django.asserts import assertTemplateUsed

from apps.users.models import Role
from config.urls import urlpatterns as project_urlpatterns
from tests.factories import UserFactory

ENGLISH = {"Accept-Language": "en"}


def boom(request):
    raise RuntimeError("Unexpected failure for the 500 page test")


# The project's URLs plus one view that always fails
urlpatterns = [path("boom/", boom), *project_urlpatterns]


@pytest.fixture(autouse=True)
def production_errors(settings):
    settings.DEBUG = False


class TestNotFoundPage:
    def test_uses_the_layout(self, client):
        response = client.get("/no-such-page/")

        assert response.status_code == 404
        assertTemplateUsed(response, "404.html")
        assertTemplateUsed(response, "web/base.html")
        assert "Página no encontrada" in response.content.decode()

    def test_english(self, client):
        response = client.get("/no-such-page/", headers=ENGLISH)

        assert "Page not found" in response.content.decode()

    @pytest.mark.django_db
    def test_keeps_the_signed_in_menu(self, client):
        client.force_login(UserFactory(role=Role.PATIENT))

        response = client.get("/no-such-page/")

        assert response.status_code == 404
        assert "Mis citas" in response.content.decode()

    @pytest.mark.django_db
    def test_a_view_404_uses_it_too(self, client):
        client.force_login(UserFactory(role=Role.PATIENT))

        response = client.get("/doctors/00000000-0000-0000-0000-000000000000/")

        assert response.status_code == 404
        assertTemplateUsed(response, "404.html")


@pytest.mark.django_db
class TestForbiddenPage:
    def test_wrong_role_gets_the_layout(self, client):
        client.force_login(UserFactory(role=Role.DOCTOR))

        response = client.get("/doctors/")

        assert response.status_code == 403
        assertTemplateUsed(response, "403.html")
        assertTemplateUsed(response, "web/base.html")
        assert "No tienes acceso a esta página." in response.content.decode()

    def test_english(self, client):
        client.force_login(UserFactory(role=Role.DOCTOR))

        response = client.get("/doctors/", headers=ENGLISH)

        assert "You don't have access to this page." in response.content.decode()


@pytest.mark.urls(__name__)
class TestServerErrorPage:
    """No django_db mark: the page must render with the database out of reach."""

    @pytest.fixture
    def client(self):
        return Client(raise_request_exception=False)

    def test_uses_the_layout_without_the_database(self, client):
        response = client.get("/boom/")

        assert response.status_code == 500
        assertTemplateUsed(response, "500.html")
        assertTemplateUsed(response, "web/base.html")
        assert "Algo salió mal" in response.content.decode()

    def test_english(self, client):
        response = client.get("/boom/", headers=ENGLISH)

        assert "Something went wrong" in response.content.decode()

    def test_shows_no_account_links(self, client):
        """Without the request it cannot know who is signed in."""
        html = client.get("/boom/").content.decode()

        assert 'href="/login/"' not in html
        assert 'action="/logout/"' not in html
        assert 'href="/"' in html
