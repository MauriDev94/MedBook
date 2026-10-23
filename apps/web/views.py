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
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.core.roles import is_admin, is_doctor
from apps.core.throttling import LoginRateThrottle, RegisterRateThrottle
from apps.doctors.services import (
    get_available_slots_week,
    list_doctors,
    list_specialties,
)
from apps.users.services import register_patient
from apps.web.forms import LoginForm, SignupForm
from apps.web.mixins import (
    HtmxPartialMixin,
    PatientRequiredMixin,
    StaffRequiredMixin,
    ThrottleMixin,
)


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


class DoctorListView(PatientRequiredMixin, HtmxPartialMixin, ListView):
    """GET /doctors/ — doctors by specialty; the HTMX filter swaps only the list."""

    template_name = "web/doctors/list.html"
    partial_template_name = "web/doctors/partials/doctor_list.html"
    context_object_name = "doctors"
    paginate_by = 10

    @property
    def selected_specialty(self) -> str:
        return self.request.GET.get("specialty", "")

    def get_queryset(self):
        return list_doctors(specialty_slug=self.selected_specialty)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["specialties"] = list_specialties()
        context["selected_specialty"] = self.selected_specialty
        return context


class DoctorDetailView(PatientRequiredMixin, HtmxPartialMixin, DetailView):
    """GET /doctors/<id>/ — profile and one week of slots; HTMX swaps the week."""

    template_name = "web/doctors/detail.html"
    partial_template_name = "web/doctors/partials/week_slots.html"
    context_object_name = "doctor"

    def get_queryset(self):
        return list_doctors()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["week"] = get_available_slots_week(self.object, self.requested_week())
        return context

    def requested_week(self) -> int:
        """`?week=` as an int; anything else shows the current week.

        The service clamps the range, like `days` in the API's available-slots.
        """
        try:
            return int(self.request.GET.get("week", 0))
        except ValueError:
            return 0
