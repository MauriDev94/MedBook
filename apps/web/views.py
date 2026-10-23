"""Web UI views — HTTP only; business rules stay in each app's services."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, TemplateView

from apps.core.roles import is_admin, is_doctor
from apps.core.throttling import LoginRateThrottle, RegisterRateThrottle
from apps.users.services import register_patient
from apps.web.forms import LoginForm, SignupForm
from apps.web.mixins import StaffRequiredMixin, ThrottleMixin


def landing_url_for(user) -> str:
    """Where a user lands after logging in or signing up.

    Doctors and admins go to the panel notice until their panel exists.
    """
    if is_doctor(user) or is_admin(user):
        return reverse("web:panel")
    return reverse("web:home")


class HomeView(TemplateView):
    """GET / — public landing page of the web UI."""

    template_name = "web/home.html"


class WebLoginView(ThrottleMixin, LoginView):
    """Session login. A safe `?next=` wins over the role-based landing page."""

    template_name = "web/auth/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True
    throttle_classes = (LoginRateThrottle,)

    def get_default_redirect_url(self):
        return landing_url_for(self.request.user)


class WebLogoutView(LogoutView):
    """POST only (Django 5 removed logout via GET)."""

    next_page = "web:home"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, _("You have logged out."))
        return response


@method_decorator(sensitive_post_parameters("password", "password_confirm"), "dispatch")
class SignupView(ThrottleMixin, FormView):
    """Patient sign-up through register_patient(); logs the new user in."""

    template_name = "web/auth/signup.html"
    form_class = SignupForm
    throttle_classes = (RegisterRateThrottle,)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(landing_url_for(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            user = register_patient(**form.registration_data())
        except ValidationError as exc:
            # The email was taken between the form check and the INSERT
            form.add_error(None, exc)
            return self.form_invalid(form)
        login(self.request, user)
        messages.success(self.request, _("Welcome to MedBook! Your account is ready."))
        return redirect(landing_url_for(user))


class PanelView(StaffRequiredMixin, TemplateView):
    """GET /panel/ — doctors and admins: their panel arrives in a later sprint."""

    template_name = "web/panel.html"
