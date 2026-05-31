"""ViewSets for the appointments app.

HTTP layer only: auth, permissions, serializer selection, response codes.
All business logic is delegated to apps.appointments.services.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.appointments import services
from apps.appointments.models import Appointment
from apps.appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentListSerializer,
    AppointmentUpdateSerializer,
)
from apps.core.permissions import (
    IsAdminRole,
    IsDoctorOfAppointment,
    IsPatient,
    IsPatientOrDoctor,
)
from apps.users.models import Role


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
        # Admin sees all
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
            # Only patients book appointments
            return [IsAuthenticated(), IsPatient()]
        if self.action in ["confirm", "complete", "no_show"]:
            # Only the assigned doctor can confirm/complete/mark no-show
            return [IsAuthenticated(), IsDoctorOfAppointment()]
        if self.action == "cancel":
            # Patient or doctor of THIS appointment can cancel
            return [IsAuthenticated(), IsPatientOrDoctor()]
        if self.action == "destroy":
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    # --- State transition actions ---

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Transition PENDING → CONFIRMED (doctor only)."""
        appointment = self.get_object()
        try:
            services.confirm_appointment(appointment, confirmed_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Transition PENDING|CONFIRMED → CANCELLED (patient or doctor)."""
        appointment = self.get_object()
        try:
            services.cancel_appointment(appointment, cancelled_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Transition CONFIRMED → COMPLETED (doctor only)."""
        appointment = self.get_object()
        try:
            services.complete_appointment(appointment)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request, pk=None):
        """Transition CONFIRMED → NO_SHOW (doctor only)."""
        appointment = self.get_object()
        try:
            services.mark_no_show(appointment)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AppointmentDetailSerializer(appointment).data)
