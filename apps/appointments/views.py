"""ViewSets for the appointments app.

HTTP layer only: auth, permissions, serializer selection, response codes.
All business logic is delegated to apps.appointments.services.
"""

from functools import wraps

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.appointments import services
from apps.appointments.models import Appointment, MedicalNote
from apps.appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentListSerializer,
    AppointmentUpdateSerializer,
    MedicalNoteSerializer,
)
from apps.core.permissions import (
    IsAdminRole,
    IsDoctorOfAppointment,
    IsPatient,
    IsPatientOrDoctor,
)
from apps.users.models import Role


def _handle_transition_error(fn):
    """Decorator: catch ValueError from state transitions and return 400."""

    @wraps(fn)
    def wrapper(self, request, *args, **kwargs):
        try:
            return fn(self, request, *args, **kwargs)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return wrapper


class AppointmentViewSet(viewsets.ModelViewSet):
    """Full CRUD for appointments, with role-based filtering and state actions."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """Filter appointments by role — patients see only theirs, doctors see theirs."""
        user = self.request.user
        qs = Appointment.objects.select_related(
            "patient__user",
            "doctor__user",
            "slot__schedule",
        )
        if user.role == Role.PATIENT:
            return qs.filter(patient__user=user)
        if user.role == Role.DOCTOR:
            return qs.filter(doctor__user=user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AppointmentCreateSerializer
        if self.action in ["update", "partial_update"]:
            return AppointmentUpdateSerializer
        if self.action == "list":
            return AppointmentListSerializer
        return AppointmentDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsPatient()]
        if self.action in ["confirm", "complete", "no_show"]:
            return [IsAuthenticated(), IsDoctorOfAppointment()]
        if self.action == "cancel":
            return [IsAuthenticated(), IsPatientOrDoctor()]
        if self.action == "destroy":
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    # --- State transition actions ---

    @action(detail=True, methods=["post"])
    @_handle_transition_error
    def confirm(self, request, pk=None):
        """Transition PENDING → CONFIRMED (doctor only)."""
        appointment = self.get_object()
        services.confirm_appointment(appointment, confirmed_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"])
    @_handle_transition_error
    def cancel(self, request, pk=None):
        """Transition PENDING|CONFIRMED → CANCELLED (patient or doctor)."""
        appointment = self.get_object()
        services.cancel_appointment(appointment, cancelled_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"])
    @_handle_transition_error
    def complete(self, request, pk=None):
        """Transition CONFIRMED → COMPLETED (doctor only)."""
        appointment = self.get_object()
        services.complete_appointment(appointment)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"], url_path="no-show")
    @_handle_transition_error
    def no_show(self, request, pk=None):
        """Transition CONFIRMED → NO_SHOW (doctor only)."""
        appointment = self.get_object()
        services.mark_no_show(appointment)
        return Response(AppointmentDetailSerializer(appointment).data)


class MedicalNoteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Read-only notes nested under /api/appointments/{appointment_pk}/notes/.

    Only the doctor assigned to the appointment and admins can access notes.
    Patients are explicitly blocked — medical notes are sensitive clinical data.
    Notes are immutable after creation (no update, no delete).
    """

    serializer_class = MedicalNoteSerializer
    permission_classes = [IsAuthenticated]

    def _get_appointment(self):
        """Resolve appointment from URL, enforcing role-based access."""
        appointment_pk = self.kwargs["appointment_pk"]
        user = self.request.user
        qs = Appointment.objects.select_related("doctor__user")

        if user.role == Role.ADMIN:
            return get_object_or_404(qs, pk=appointment_pk)

        if user.role == Role.DOCTOR:
            return get_object_or_404(qs, pk=appointment_pk, doctor__user=user)

        raise PermissionDenied("Only doctors and admins can access medical notes.")

    def get_queryset(self):
        appointment = self._get_appointment()
        return MedicalNote.objects.filter(appointment=appointment).select_related(
            "author"
        )

    def perform_create(self, serializer):
        appointment = self._get_appointment()
        serializer.save(appointment=appointment, author=self.request.user)
