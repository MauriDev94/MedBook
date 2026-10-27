"""Web UI views — HTTP only; business rules stay in each app's services."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django_htmx.http import HttpResponseClientRedirect, reswap, retarget

from apps.appointments.models import InvalidTransition
from apps.appointments.services import (
    appointments_visible_to,
    cancel_appointment,
    create_appointment,
    list_past_appointments,
    list_time_slots,
    list_upcoming_appointments,
    validate_appointment_booking,
)
from apps.core.exceptions import SlotConflict
from apps.core.roles import is_admin, is_doctor
from apps.core.throttling import LoginRateThrottle, RegisterRateThrottle
from apps.core.utils import moment_of
from apps.doctors.services import (
    get_available_slots_week,
    list_doctors,
    list_specialties,
    week_of,
)
from apps.users.services import register_patient
from apps.web.forms import BookingForm, LoginForm, SignupForm
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


# The API answers SlotConflict with its own detail; the web says what happened
SLOT_TAKEN_MESSAGE = gettext_lazy("Another patient just booked this time.")


def booked_message(slot) -> str:
    """The success message, with the day and time in Chilean time."""
    return _(
        "Your appointment on %(weekday)s, %(date)s at %(time)s is booked. "
        "We sent you an email with the details."
    ) % moment_of(slot)


class BookSlotView(PatientRequiredMixin, HtmxPartialMixin, SingleObjectMixin, FormView):
    """GET/POST /slots/<id>/book/ — confirm and book one slot.

    A slot on the doctor's page loads this form into the booking dialog
    (HTMX); any other request gets a full page, so booking also works
    without JavaScript. Booking goes back to the doctor's page on the slot's
    week. A slot that can no longer be booked sends the page back there with
    the reason; the dialog shows it and refreshes the week behind it.
    """

    template_name = "web/booking/confirm.html"
    partial_template_name = "web/booking/partials/dialog.html"
    form_class = BookingForm
    context_object_name = "slot"

    def get_queryset(self):
        return list_time_slots()

    @property
    def patient(self):
        return self.request.user.patient_profile

    @property
    def doctor(self):
        return self.object.schedule.doctor

    @property
    def slot_week(self) -> int:
        return week_of(timezone.localdate(self.object.start_datetime))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            validate_appointment_booking(self.patient, self.object)
        except ValidationError as exc:
            return self.booking_failed(exc.messages[0])
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "patient": self.patient,
            "slot": self.object,
        }

    def get_context_data(self, **kwargs):
        return super().get_context_data(doctor=self.doctor, **kwargs)

    def form_valid(self, form):
        try:
            create_appointment(
                patient=self.patient,
                slot=self.object,
                reason=form.cleaned_data["reason"],
            )
        except SlotConflict:
            return self.booking_failed(SLOT_TAKEN_MESSAGE)
        messages.success(self.request, booked_message(self.object))
        return self.redirect_to(reverse("web:appointment_list"))

    def form_invalid(self, form):
        # The only field is optional: an invalid form is a booking rule that failed
        return self.booking_failed(form.non_field_errors()[0])

    def booking_failed(self, message):
        if self.request.htmx:
            context = {
                "slot": self.object,
                "doctor": self.doctor,
                "error": message,
                "week": get_available_slots_week(self.doctor, self.slot_week),
            }
            response = render(self.request, self.partial_template_name, context)
            patch_vary_headers(response, ("HX-Request",))
            return response
        messages.error(self.request, message)
        return self.back_to_doctor()

    def back_to_doctor(self):
        url = reverse("web:doctor_detail", args=[self.doctor.pk])
        return self.redirect_to(f"{url}?week={self.slot_week}")

    def redirect_to(self, url):
        if self.request.htmx:
            # A full page load: the message shows and the dialog goes away
            return HttpResponseClientRedirect(url)
        return redirect(url)


class AppointmentListView(PatientRequiredMixin, HtmxPartialMixin, ListView):
    """GET /appointments/ — the patient's appointments, upcoming or past.

    `?tab=past` lists the ones that already started; anything else, the
    upcoming ones. The tabs and the pagination swap only the list (HTMX).
    """

    template_name = "web/appointments/list.html"
    partial_template_name = "web/appointments/partials/appointment_list.html"
    context_object_name = "appointments"
    paginate_by = 10

    @property
    def tab(self) -> str:
        return "past" if self.request.GET.get("tab") == "past" else "upcoming"

    def get_queryset(self):
        if self.tab == "past":
            return list_past_appointments(self.request.user)
        return list_upcoming_appointments(self.request.user)

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab=self.tab, **kwargs)


class AppointmentDetailView(PatientRequiredMixin, DetailView):
    """GET /appointments/<id>/ — one of the patient's appointments."""

    template_name = "web/appointments/detail.html"
    context_object_name = "appointment"

    def get_queryset(self):
        return appointments_visible_to(self.request.user)


# The service raises InvalidTransition in English; the web says it plainly
CANNOT_CANCEL_MESSAGE = gettext_lazy("This appointment can no longer be cancelled.")


def cancelled_message(appointment) -> str:
    return _(
        "Your appointment on %(weekday)s, %(date)s at %(time)s is cancelled."
    ) % moment_of(appointment.slot)


class CancelAppointmentView(
    PatientRequiredMixin, HtmxPartialMixin, SingleObjectMixin, TemplateView
):
    """GET/POST /appointments/<id>/cancel/ — confirm, then cancel.

    The cancel link loads the confirmation into the cancel dialog (HTMX); any
    other request gets a full page. Cancelling calls cancel_appointment().
    With HTMX the answer replaces the appointment's status where the page
    shows it (list row or detail page) and adds the message; dialog.js closes
    the dialog. Without JavaScript it goes to the appointment's page.
    """

    template_name = "web/appointments/cancel.html"
    partial_template_name = "web/appointments/partials/cancel_dialog.html"
    context_object_name = "appointment"

    def get_queryset(self):
        return appointments_visible_to(self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.can_be_cancelled():
            return self.cancel_failed()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            cancel_appointment(self.object, cancelled_by=request.user)
        except InvalidTransition:
            return self.cancel_failed()
        messages.success(request, cancelled_message(self.object))
        if not request.htmx:
            return redirect("web:appointment_detail", pk=self.object.pk)
        context = {"appointment": self.object}
        response = render(request, "web/appointments/partials/cancelled.html", context)
        response = retarget(response, f"#appointment-{self.object.pk}-status")
        return reswap(response, "outerHTML")

    def cancel_failed(self):
        if self.request.htmx:
            context = {"appointment": self.object, "error": CANNOT_CANCEL_MESSAGE}
            response = render(self.request, self.partial_template_name, context)
            patch_vary_headers(response, ("HX-Request",))
            return response
        messages.error(self.request, CANNOT_CANCEL_MESSAGE)
        return redirect("web:appointment_detail", pk=self.object.pk)
