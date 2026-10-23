"""Web UI language tests (Paso 24, ADR 0002).

The UI is Spanish by default and English on request. LocaleMiddleware picks
the language from the cookie set by `set_language`, then from
Accept-Language. URLs carry no language prefix.
"""

import pytest
from django.conf import settings

HOME_URL = "/"
SET_LANGUAGE_URL = "/i18n/setlang/"
SPANISH_HEADING = "Reserva tu hora médica"
ENGLISH_HEADING = "Book your medical appointment"


class TestWebLanguage:
    def test_spanish_by_default(self, client):
        response = client.get(HOME_URL)
        html = response.content.decode()

        assert SPANISH_HEADING in html
        assert '<html lang="es">' in html
        assert response["Content-Language"] == "es"

    @pytest.mark.parametrize("header", ["es", "es-CL", "es-CL,es;q=0.9,en;q=0.8"])
    def test_spanish_accept_language(self, client, header):
        response = client.get(HOME_URL, headers={"Accept-Language": header})

        assert SPANISH_HEADING in response.content.decode()

    @pytest.mark.parametrize("header", ["en", "en-US", "en-US,en;q=0.9"])
    def test_english_accept_language(self, client, header):
        response = client.get(HOME_URL, headers={"Accept-Language": header})
        html = response.content.decode()

        assert ENGLISH_HEADING in html
        assert '<html lang="en">' in html

    def test_unsupported_language_falls_back_to_spanish(self, client):
        response = client.get(HOME_URL, headers={"Accept-Language": "fr"})

        assert SPANISH_HEADING in response.content.decode()


class TestLanguageSwitcher:
    def test_switcher_posts_to_set_language(self, client):
        html = client.get(HOME_URL).content.decode()

        assert f'action="{SET_LANGUAGE_URL}"' in html
        assert 'name="language"' in html

    def test_switcher_sets_language_cookie(self, client):
        response = client.post(SET_LANGUAGE_URL, {"language": "en", "next": "/"})

        assert response.status_code == 302
        assert response["Location"] == "/"
        assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"

    def test_cookie_wins_over_accept_language(self, client):
        client.post(SET_LANGUAGE_URL, {"language": "en", "next": "/"})

        response = client.get(HOME_URL, headers={"Accept-Language": "es"})

        assert ENGLISH_HEADING in response.content.decode()
