"""Tests for apps/core/permissions.py — 100% coverage required.

Each permission class gets at least one positive test (returns True)
and one negative test (returns False).
Uses APIRequestFactory to build minimal request objects without hitting
any URL or view logic.
"""

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.core.permissions import (
    IsAdminRole,
    IsDoctor,
    IsDoctorOfAppointment,
    IsOwnerOrAdmin,
    IsPatient,
    IsPatientOfAppointment,
    IsPatientOrDoctor,
    ReadOnly,
)
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    UserFactory,
)
from apps.users.models import Role

factory_req = APIRequestFactory()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_request(method="GET", user=None):
    """Return a minimal request with the given user attached."""
    request = getattr(factory_req, method.lower())("/fake/")
    request.user = user or AnonymousUser()
    return request


# ---------------------------------------------------------------------------
# IsDoctor
# ---------------------------------------------------------------------------


class TestIsDoctor:
    perm = IsDoctor()

    def test_doctor_user_is_allowed(self, db):
        """Authenticated user with role=DOCTOR passes."""
        user = UserFactory(role=Role.DOCTOR)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is True

    def test_patient_user_is_denied(self, db):
        """Authenticated user with role=PATIENT is rejected."""
        user = UserFactory(role=Role.PATIENT)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is False

    def test_unauthenticated_is_denied(self):
        """Anonymous request is rejected."""
        request = make_request(user=AnonymousUser())
        assert self.perm.has_permission(request, None) is False


# ---------------------------------------------------------------------------
# IsPatient
# ---------------------------------------------------------------------------


class TestIsPatient:
    perm = IsPatient()

    def test_patient_user_is_allowed(self, db):
        """Authenticated user with role=PATIENT passes."""
        user = UserFactory(role=Role.PATIENT)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is True

    def test_doctor_user_is_denied(self, db):
        """Authenticated user with role=DOCTOR is rejected."""
        user = UserFactory(role=Role.DOCTOR)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is False

    def test_unauthenticated_is_denied(self):
        """Anonymous request is rejected."""
        request = make_request(user=AnonymousUser())
        assert self.perm.has_permission(request, None) is False


# ---------------------------------------------------------------------------
# IsAdminRole
# ---------------------------------------------------------------------------


class TestIsAdminRole:
    perm = IsAdminRole()

    def test_admin_user_is_allowed(self, db):
        """Authenticated user with role=ADMIN passes."""
        user = UserFactory(role=Role.ADMIN, is_staff=True)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is True

    def test_doctor_user_is_denied(self, db):
        """Authenticated doctor is rejected."""
        user = UserFactory(role=Role.DOCTOR)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is False

    def test_unauthenticated_is_denied(self):
        """Anonymous request is rejected."""
        request = make_request(user=AnonymousUser())
        assert self.perm.has_permission(request, None) is False


# ---------------------------------------------------------------------------
# IsOwnerOrAdmin
# ---------------------------------------------------------------------------


class TestIsOwnerOrAdmin:
    perm = IsOwnerOrAdmin()

    def test_owner_can_access_own_object(self, db):
        """User accessing their own object passes has_object_permission."""
        user = UserFactory()
        request = make_request(user=user)
        # obj IS the user directly
        assert self.perm.has_object_permission(request, None, user) is True

    def test_admin_can_access_any_object(self, db):
        """Admin user can access any object."""
        admin = UserFactory(role=Role.ADMIN, is_staff=True)
        other_user = UserFactory()
        request = make_request(user=admin)
        assert self.perm.has_object_permission(request, None, other_user) is True

    def test_non_owner_is_denied(self, db):
        """User accessing another user's object is rejected."""
        user = UserFactory()
        other_user = UserFactory()
        request = make_request(user=user)
        assert self.perm.has_object_permission(request, None, other_user) is False

    def test_owner_via_user_fk(self, db):
        """Object with .user FK — owner access passes."""
        patient = PatientFactory()
        request = make_request(user=patient.user)
        # obj has a .user attribute pointing to patient.user
        assert self.perm.has_object_permission(request, None, patient) is True


# ---------------------------------------------------------------------------
# IsDoctorOfAppointment
# ---------------------------------------------------------------------------


class TestIsDoctorOfAppointment:
    perm = IsDoctorOfAppointment()

    def test_assigned_doctor_can_access(self, db):
        """Doctor assigned to the appointment passes."""
        appt = AppointmentFactory()
        doctor_user = appt.doctor.user
        request = make_request(user=doctor_user)
        assert self.perm.has_object_permission(request, None, appt) is True

    def test_other_doctor_is_denied(self, db):
        """A different doctor is rejected."""
        appt = AppointmentFactory()
        other_doctor = DoctorFactory()
        request = make_request(user=other_doctor.user)
        assert self.perm.has_object_permission(request, None, appt) is False

    def test_patient_is_denied(self, db):
        """Patient user is rejected — has no doctor_profile."""
        appt = AppointmentFactory()
        patient_user = appt.patient.user
        request = make_request(user=patient_user)
        assert self.perm.has_object_permission(request, None, appt) is False


# ---------------------------------------------------------------------------
# IsPatientOfAppointment
# ---------------------------------------------------------------------------


class TestIsPatientOfAppointment:
    perm = IsPatientOfAppointment()

    def test_assigned_patient_can_access(self, db):
        """Patient who booked the appointment passes."""
        appt = AppointmentFactory()
        patient_user = appt.patient.user
        request = make_request(user=patient_user)
        assert self.perm.has_object_permission(request, None, appt) is True

    def test_other_patient_is_denied(self, db):
        """A different patient is rejected."""
        appt = AppointmentFactory()
        other_patient = PatientFactory()
        request = make_request(user=other_patient.user)
        assert self.perm.has_object_permission(request, None, appt) is False

    def test_doctor_is_denied(self, db):
        """Doctor user is rejected — has no patient_profile."""
        appt = AppointmentFactory()
        doctor_user = appt.doctor.user
        request = make_request(user=doctor_user)
        assert self.perm.has_object_permission(request, None, appt) is False


# ---------------------------------------------------------------------------
# IsPatientOrDoctor
# ---------------------------------------------------------------------------


class TestIsPatientOrDoctor:
    perm = IsPatientOrDoctor()

    def test_patient_is_allowed(self, db):
        """Patient role passes."""
        user = UserFactory(role=Role.PATIENT)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is True

    def test_doctor_is_allowed(self, db):
        """Doctor role passes."""
        user = UserFactory(role=Role.DOCTOR)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is True

    def test_admin_is_denied(self, db):
        """Admin role is rejected — not patient or doctor."""
        user = UserFactory(role=Role.ADMIN, is_staff=True)
        request = make_request(user=user)
        assert self.perm.has_permission(request, None) is False

    def test_unauthenticated_is_denied(self):
        """Anonymous request is rejected."""
        request = make_request(user=AnonymousUser())
        assert self.perm.has_permission(request, None) is False


# ---------------------------------------------------------------------------
# ReadOnly
# ---------------------------------------------------------------------------


class TestReadOnly:
    perm = ReadOnly()

    def test_get_is_allowed(self, db):
        """GET method passes."""
        user = UserFactory()
        request = make_request(method="GET", user=user)
        assert self.perm.has_permission(request, None) is True

    def test_head_is_allowed(self, db):
        """HEAD method passes."""
        user = UserFactory()
        request = make_request(method="HEAD", user=user)
        assert self.perm.has_permission(request, None) is True

    def test_options_is_allowed(self, db):
        """OPTIONS method passes."""
        user = UserFactory()
        request = make_request(method="OPTIONS", user=user)
        assert self.perm.has_permission(request, None) is True

    def test_post_is_denied(self, db):
        """POST method is rejected."""
        user = UserFactory()
        request = make_request(method="POST", user=user)
        assert self.perm.has_permission(request, None) is False

    def test_put_is_denied(self, db):
        """PUT method is rejected."""
        user = UserFactory()
        request = make_request(method="PUT", user=user)
        assert self.perm.has_permission(request, None) is False

    def test_delete_is_denied(self, db):
        """DELETE method is rejected."""
        user = UserFactory()
        request = make_request(method="DELETE", user=user)
        assert self.perm.has_permission(request, None) is False

    def test_patch_is_denied(self, db):
        """PATCH (partial update) is rejected — it's a write method."""
        user = UserFactory()
        request = make_request(method="PATCH", user=user)
        assert self.perm.has_permission(request, None) is False
