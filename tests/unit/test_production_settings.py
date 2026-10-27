"""Production settings that are easy to break without noticing.

Middleware stays in sync with base (Paso 24): production.py used to redefine
MIDDLEWARE from scratch, so any middleware added to base.py (LocaleMiddleware,
HtmxMiddleware) silently went missing in production. It now inserts
WhiteNoise into base's list instead.

The health check answers itself (Paso 39): Render counts any 3xx as healthy,
so a redirect to HTTPS would pass without /health/ ever querying the DB.
"""

import importlib

import pytest

from config.settings import base


@pytest.fixture
def production_settings(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", ".onrender.com")
    return importlib.import_module("config.settings.production")


def test_production_keeps_every_base_middleware_in_order(production_settings):
    production = [
        m
        for m in production_settings.MIDDLEWARE
        if m != "whitenoise.middleware.WhiteNoiseMiddleware"
    ]

    assert production == base.MIDDLEWARE


def test_whitenoise_comes_right_after_security_middleware(production_settings):
    middleware = production_settings.MIDDLEWARE
    security = middleware.index("django.middleware.security.SecurityMiddleware")

    assert middleware[security + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"


@pytest.mark.django_db
def test_health_check_is_not_redirected_to_https(production_settings, client, settings):
    settings.SECURE_SSL_REDIRECT = production_settings.SECURE_SSL_REDIRECT
    settings.SECURE_REDIRECT_EXEMPT = production_settings.SECURE_REDIRECT_EXEMPT

    assert client.get("/health/").json() == {"status": "ok", "database": "ok"}
    assert client.get("/").status_code == 301
