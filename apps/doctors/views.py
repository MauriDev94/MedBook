"""ViewSets for the doctors app.

Each ViewSet handles HTTP concerns only: auth, permissions, serialization,
and response codes. No ORM calls or business logic lives here.
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.appointments.serializers import TimeSlotSerializer
from apps.core.permissions import IsDoctor
from apps.doctors.filters import DoctorFilter, ScheduleFilter
from apps.doctors.models import Doctor, Schedule, Specialty
from apps.doctors.serializers import (
    DoctorDetailSerializer,
    DoctorListSerializer,
    ScheduleCreateSerializer,
    ScheduleSerializer,
    SpecialtySerializer,
)
from apps.doctors.services import get_available_slots
from apps.users.models import Role


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only doctor profiles.

    Doctors are created via admin — not via API.
    Filtering, searching and ordering are supported.
    """

    queryset = Doctor.objects.select_related("user").prefetch_related("specialties")
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = DoctorFilter
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    ordering_fields = ["user__last_name", "consultation_duration"]
    ordering = ["user__last_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return DoctorListSerializer
        return DoctorDetailSerializer

    @extend_schema(
        summary="List available time slots for a doctor",
        parameters=[
            OpenApiParameter(
                "days", int, description="Days ahead to look (1–365, default 7)"
            )
        ],
        responses=TimeSlotSerializer(many=True),
        tags=["doctors"],
    )
    @action(detail=True, methods=["get"], url_path="available-slots")
    def available_slots(self, request, pk=None):
        """Return available time slots for this doctor.

        Query params:
            days (int): days ahead to look (1–365, default 7)
        """
        doctor = self.get_object()
        days_ahead = self._parse_days(request.query_params.get("days", 7))
        slots = get_available_slots(doctor, days_ahead=days_ahead)
        return Response(TimeSlotSerializer(slots, many=True).data)

    @staticmethod
    def _parse_days(raw) -> int:
        """Parse the ?days= query param, returning 400 on non-integer input.

        Range clamping (1–365) is handled by the service; this only guards
        the int() conversion so bad input returns 400 instead of crashing 500.
        """
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValidationError({"days": "Must be an integer."})


class ScheduleViewSet(viewsets.ModelViewSet):
    """CRUD for doctor schedules.

    Doctors manage their own schedules only. Admins can manage all.
    Patients see an empty queryset (404 on any access attempt).

    DELETE performs a soft delete (is_active=False) — schedules are
    never physically removed so slot history is preserved.
    """

    permission_classes = [IsAuthenticated]
    filterset_class = ScheduleFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Schedule.objects.none()
        user = self.request.user
        qs = Schedule.objects.select_related("doctor__user").order_by(
            "doctor", "day_of_week", "start_time"
        )
        if user.role == Role.ADMIN:
            return qs
        if user.role == Role.DOCTOR:
            return qs.filter(doctor__user=user)
        return qs.none()

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsDoctor()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ScheduleCreateSerializer
        return ScheduleSerializer

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user.doctor_profile)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only specialties — created via data migration, not API."""

    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    permission_classes = [IsAuthenticated]
