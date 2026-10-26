"""Web RBAC mixins (Paso 25, ADR 0002).

Anonymous visitors are sent to the login page; a signed-in user with the
wrong role gets 403. Each mixin uses the same role predicates as the DRF
permission classes (apps.core.roles).
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View
from django_htmx.middleware import HtmxDetails

from apps.users.models import Role
from apps.web.mixins import PatientRequiredMixin, StaffRequiredMixin
from tests.factories import UserFactory


class PatientOnlyView(PatientRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


class StaffOnlyView(StaffRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


HTMX = {"HX-Request": "true"}


def call(view_class, user, headers=None):
    request = RequestFactory().get("/protected/", headers=headers)
    request.user = user
    request.htmx = HtmxDetails(request)  # what HtmxMiddleware sets
    return view_class.as_view()(request)


@pytest.mark.django_db
class TestPatientRequiredMixin:
    def test_patient_is_allowed(self):
        response = call(PatientOnlyView, UserFactory(role=Role.PATIENT))

        assert response.status_code == 200

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_other_roles_are_forbidden(self, role):
        with pytest.raises(PermissionDenied):
            call(PatientOnlyView, UserFactory(role=role))

    def test_anonymous_is_sent_to_login(self):
        response = call(PatientOnlyView, AnonymousUser())

        assert response.status_code == 302
        assert response["Location"] == "/login/?next=/protected/"


@pytest.mark.django_db
class TestStaffRequiredMixin:
    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_doctor_and_admin_are_allowed(self, role):
        response = call(StaffOnlyView, UserFactory(role=role))

        assert response.status_code == 200

    def test_patient_is_forbidden(self):
        with pytest.raises(PermissionDenied):
            call(StaffOnlyView, UserFactory(role=Role.PATIENT))

    def test_anonymous_is_sent_to_login(self):
        response = call(StaffOnlyView, AnonymousUser())

        assert response.status_code == 302
        assert response["Location"] == "/login/?next=/protected/"


@pytest.mark.django_db
class TestSessionExpiredDuringHtmx:
    """An HTMX request whose session expired would swap the login page into
    the dialog or list it targets; instead the whole page goes to login.
    """

    def test_sends_the_whole_page_to_login_and_back(self):
        headers = {**HTMX, "HX-Current-URL": "http://testserver/doctors/42/?week=1"}

        response = call(PatientOnlyView, AnonymousUser(), headers=headers)

        assert response.status_code == 200
        assert response["HX-Redirect"] == "/login/?next=/doctors/42/%3Fweek%3D1"

    def test_without_the_current_url_comes_back_to_the_request(self):
        response = call(PatientOnlyView, AnonymousUser(), headers=HTMX)

        assert response["HX-Redirect"] == "/login/?next=/protected/"

    def test_another_site_is_never_the_next_page(self):
        headers = {**HTMX, "HX-Current-URL": "https://evil.example/phish/"}

        response = call(PatientOnlyView, AnonymousUser(), headers=headers)

        assert response["HX-Redirect"] == "/login/?next=/protected/"

    def test_wrong_role_still_gets_403(self):
        with pytest.raises(PermissionDenied):
            call(PatientOnlyView, UserFactory(role=Role.DOCTOR), headers=HTMX)
