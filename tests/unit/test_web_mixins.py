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

from apps.users.models import Role
from apps.web.mixins import PatientRequiredMixin, StaffRequiredMixin
from tests.factories import UserFactory


class PatientOnlyView(PatientRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


class StaffOnlyView(StaffRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


def call(view_class, user):
    request = RequestFactory().get("/protected/")
    request.user = user
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
