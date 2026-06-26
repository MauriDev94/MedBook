"""ViewSets for the appointments app.

HTTP layer only: auth, permissions, serializer selection, response codes.
All business logic is delegated to apps.appointments.services.
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.appointments import services
from apps.appointments.filters import AppointmentFilter
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
    IsDoctorOrAdminForNote,
    IsPatient,
    IsPatientOfAppointment,
)
from apps.users.models import Role


class AppointmentViewSet(viewsets.ModelViewSet):
    """Full CRUD for appointments, with role-based filtering and state actions."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AppointmentFilter

    def get_queryset(self):
        """Filter appointments by role — patients see only theirs, doctors see theirs."""
        if getattr(self, "swagger_fake_view", False):
            return Appointment.objects.none()
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
            # Ownership enforced at the object level (defense-in-depth):
            # either the patient who booked it or the assigned doctor.
            return [
                IsAuthenticated(),
                (IsPatientOfAppointment | IsDoctorOfAppointment)(),
            ]
        if self.action == "destroy":
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Book an appointment, returning the full detail representation.

        The write serializer only accepts {slot, reason}; the response uses
        AppointmentDetailSerializer so clients get back the complete created
        resource (status, can_cancel, nested slot, etc.) without a follow-up
        GET.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()
        detail = AppointmentDetailSerializer(
            appointment, context=self.get_serializer_context()
        )
        return Response(detail.data, status=status.HTTP_201_CREATED)

    # --- State transition actions ---

    @extend_schema(
        request=None,
        responses={
            200: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Invalid transition"),
        },
        summary="Confirm appointment (doctor only)",
        tags=["appointments"],
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Transition PENDING → CONFIRMED (doctor only)."""
        appointment = self.get_object()
        services.confirm_appointment(appointment, confirmed_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)

    @extend_schema(
        request=None,
        responses={
            200: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Invalid transition"),
        },
        summary="Cancel appointment (patient or doctor)",
        tags=["appointments"],
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Transition PENDING|CONFIRMED → CANCELLED (patient or doctor)."""
        appointment = self.get_object()
        services.cancel_appointment(appointment, cancelled_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)

    @extend_schema(
        request=None,
        responses={
            200: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Invalid transition"),
        },
        summary="Complete appointment (doctor only)",
        tags=["appointments"],
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Transition CONFIRMED → COMPLETED (doctor only)."""
        appointment = self.get_object()
        services.complete_appointment(appointment, completed_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)

    @extend_schema(
        request=None,
        responses={
            200: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Invalid transition"),
        },
        summary="Mark appointment as no-show (doctor only)",
        tags=["appointments"],
    )
    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request, pk=None):
        """Transition CONFIRMED → NO_SHOW (doctor only)."""
        appointment = self.get_object()
        services.mark_no_show(appointment, marked_by=request.user)
        return Response(AppointmentDetailSerializer(appointment).data)


@extend_schema(tags=["notes"])
class MedicalNoteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Medical notes nested under /api/appointments/{appointment_pk}/notes/.

    Only the doctor assigned to the appointment and admins can access notes.
    Patients are explicitly blocked — medical notes are sensitive clinical data.
    Notes are immutable after creation (no update, no delete).
    """

    serializer_class = MedicalNoteSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrAdminForNote]

    def _get_appointment(self):
        """Resolve the appointment from the URL, scoped by role.

        Role + doctor-ownership are already enforced by
        IsDoctorOrAdminForNote.has_permission() before this runs. This only
        re-derives the same scoping to fetch the object for queryset
        filtering and note creation — admins see any appointment, doctors
        only their own.
        """
        appointment_pk = self.kwargs["appointment_pk"]
        user = self.request.user
        qs = Appointment.objects.select_related("doctor__user")

        if user.role == Role.ADMIN:
            return get_object_or_404(qs, pk=appointment_pk)

        return get_object_or_404(qs, pk=appointment_pk, doctor__user=user)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MedicalNote.objects.none()
        appointment = self._get_appointment()
        return MedicalNote.objects.filter(appointment=appointment).select_related(
            "author"
        )

    def perform_create(self, serializer):
        appointment = self._get_appointment()
        serializer.save(appointment=appointment, author=self.request.user)
