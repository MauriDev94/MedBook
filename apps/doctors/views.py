"""ViewSets for the doctors app.

Each ViewSet handles HTTP concerns only: auth, permissions, serialization,
and response codes. No ORM calls or business logic lives here.
"""

import datetime

from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.appointments.models import TimeSlot
from apps.appointments.serializers import TimeSlotSerializer
from apps.doctors.models import Doctor, Specialty
from apps.doctors.serializers import (
    DoctorDetailSerializer,
    DoctorListSerializer,
    SpecialtySerializer,
)


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only doctor profiles.

    Doctors are created via admin — not via API.
    Filtering, searching and ordering are supported.
    """

    queryset = Doctor.objects.select_related("user").prefetch_related("specialties")
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    ordering_fields = ["user__last_name", "consultation_duration"]
    ordering = ["user__last_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return DoctorListSerializer
        return DoctorDetailSerializer

    @action(detail=True, methods=["get"], url_path="available-slots")
    def available_slots(self, request, pk=None):
        """Return available time slots for this doctor.

        Query params:
            days (int): days ahead to look, default 7
        """
        doctor = self.get_object()
        days_ahead = int(request.query_params.get("days", 7))
        today = datetime.date.today()
        end_date = today + datetime.timedelta(days=days_ahead)

        slots = TimeSlot.objects.filter(
            schedule__doctor=doctor,
            status=TimeSlot.Status.AVAILABLE,
            start_datetime__date__gte=today,
            start_datetime__date__lte=end_date,
        ).order_by("start_datetime")

        serializer = TimeSlotSerializer(slots, many=True)
        return Response(serializer.data)


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only specialties — created via data migration, not API."""

    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    permission_classes = [IsAuthenticated]
