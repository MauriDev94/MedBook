"""RBAC permission classes for MedBook.

Each class has a single responsibility (SRP). No business logic lives here —
only identity/role checks and ownership comparisons.

Hierarchy:
  has_permission  → view-level check (runs before the object is fetched)
  has_object_permission → instance-level check (runs after get_object())

Role checks go through apps.core.roles, shared with the web UI's mixins.
"""

from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission

from apps.core.roles import is_admin, is_doctor, is_patient


class IsDoctor(BasePermission):
    """Allow access only to authenticated users with role=DOCTOR."""

    message = "Only doctors can perform this action."

    def has_permission(self, request, view):
        return is_doctor(request.user)


class IsPatient(BasePermission):
    """Allow access only to authenticated users with role=PATIENT."""

    message = "Only patients can perform this action."

    def has_permission(self, request, view):
        return is_patient(request.user)


class IsAdminRole(BasePermission):
    """Allow access only to authenticated users with role=ADMIN."""

    message = "Only admin users can perform this action."

    def has_permission(self, request, view):
        return is_admin(request.user)


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


class IsDoctorOrAdminForNote(BasePermission):
    """Allow access to medical notes only to admins and the assigned doctor.

    Resolves the appointment from `view.kwargs["appointment_pk"]` (the nested
    notes route). Admins may access any appointment's notes; a doctor may
    only access notes for an appointment they are assigned to. Doctors who
    are not the assigned one get the SAME 404 a nonexistent appointment_pk
    would produce (via get_object_or_404), so this never leaks whether the
    appointment exists to an unrelated doctor. Patients are rejected by role
    alone, before the appointment is even resolved, yielding 403.
    """

    message = "Only doctors and admins can access medical notes."

    def has_permission(self, request, view):
        user = request.user
        if is_admin(user):
            return True
        if not is_doctor(user):
            return False

        from apps.appointments.models import Appointment

        appointment_pk = view.kwargs["appointment_pk"]
        get_object_or_404(
            Appointment.objects.select_related("doctor__user"),
            pk=appointment_pk,
            doctor__user=user,
        )
        return True
