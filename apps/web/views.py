"""Web UI views — HTTP only; business rules stay in each app's services."""

from django.views.generic import TemplateView


class HomeView(TemplateView):
    """GET / — public landing page of the web UI."""

    template_name = "web/home.html"
