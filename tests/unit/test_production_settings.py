"""Production middleware stays in sync with base (Paso 24).

production.py used to redefine MIDDLEWARE from scratch, so any middleware
added to base.py (LocaleMiddleware, HtmxMiddleware) silently went missing in
production. It now inserts WhiteNoise into base's list instead.
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
