"""Core middleware shared by the API and the web UI."""

from django.utils import translation

API_PATH_PREFIX = "/api/"


class EnglishApiMiddleware:
    """Keep the JSON API in English whatever language the request asks for.

    The web UI is translated (ADR 0002), but API messages are part of a
    stable contract for API clients. Must run after LocaleMiddleware, which
    has already activated the visitor's language by then.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(API_PATH_PREFIX):
            translation.activate("en")
            request.LANGUAGE_CODE = "en"
        return self.get_response(request)
