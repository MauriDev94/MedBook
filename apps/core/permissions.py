"""RBAC permission classes for MedBook.

Each class has a single responsibility (SRP). No business logic lives here —
only identity/role checks and ownership comparisons.

Hierarchy:
  has_permission  → view-level check (runs before the object is fetched)
  has_object_permission → instance-level check (runs after get_object())
"""

from rest_framework.permissions import BasePermission

from apps.users.models import Role


class IsDoctor(BasePermission):
    """Allow access only to authenticated users with role=DOCTOR."""

    message = "Only doctors can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.DOCTOR
        )


class IsPatient(BasePermission):
    """Allow access only to authenticated users with role=PATIENT."""

    message = "Only patients can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.PATIENT
        )


class IsAdminRole(BasePermission):
    """Allow access only to authenticated users with role=ADMIN."""

    message = "Only admin users can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )


class IsOwnerOrAdmin(BasePermission):
    """Allow object access to the owner or to admin users.

    Reusable RBAC building block — NOT currently wired to a ViewSet. Kept as
    part of the permission toolkit because it demonstrates the dual-shape
    ownership pattern (obj is the user, or obj has a .user FK). Reserve for a
    future Patient/Doctor profile detail endpoint.

    Supports two object shapes:
    - obj IS the user (e.g. accessing User directly)
    - obj has a .user FK (e.g. Patient, Doctor profiles)
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user.role == Role.ADMIN:
            return True
        owner = getattr(obj, "user", obj)
        return owner == request.user


class IsDoctorOfAppointment(BasePermission):
    """Allow object access only to the doctor assigned to the appointment."""

    message = "You are not the doctor for this appointment."

    def has_object_permission(self, request, view, obj):
        return bool(
            hasattr(request.user, "doctor_profile")
            and obj.doctor == request.user.doctor_profile
        )


class IsPatientOfAppointment(BasePermission):
    """Allow object access only to the patient who booked the appointment."""

    message = "You are not the patient for this appointment."

    def has_object_permission(self, request, view, obj):
        return bool(
            hasattr(request.user, "patient_profile")
            and obj.patient == request.user.patient_profile
        )


class ReadOnly(BasePermission):
    """Allow GET, HEAD, OPTIONS. Block all write methods.

    Reusable RBAC building block — NOT currently wired to a ViewSet (the
    read-only ViewSets use DRF's ReadOnlyModelViewSet instead). Kept as part
    of the permission toolkit because it composes cleanly via OR, e.g.
    `(ReadOnly | IsAdminRole)` = "everyone reads, only admin writes".
    """

    def has_permission(self, request, view):
        return request.method in ("GET", "HEAD", "OPTIONS")
