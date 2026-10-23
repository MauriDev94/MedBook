from django.apps import AppConfig


class WebConfig(AppConfig):
    """Server-rendered web UI (ADR 0002): templates, forms, views, no models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.web"
    verbose_name = "Web"
