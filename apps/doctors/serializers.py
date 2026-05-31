"""Serializers for the doctors app."""

from rest_framework import serializers

from apps.core.utils import get_display_name
from apps.doctors.models import Doctor, Schedule, Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name", "slug"]


class DoctorListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — avoids heavy joins."""

    full_name = serializers.SerializerMethodField()
    specialties_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = ["id", "full_name", "consultation_duration", "specialties_count"]

    def get_full_name(self, obj) -> str:
        return get_display_name(obj.user)

    def get_specialties_count(self, obj) -> int:
        # Uses prefetch_related cache when available — no extra query
        return obj.specialties.count()


class DoctorDetailSerializer(serializers.ModelSerializer):
    """Full representation for retrieve views."""

    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)

    class Meta:
        model = Doctor
        fields = [
            "id",
            "full_name",
            "email",
            "license_number",
            "bio",
            "consultation_duration",
            "specialties",
            "created_at",
        ]

    def get_full_name(self, obj) -> str:
        return get_display_name(obj.user)


class ScheduleSerializer(serializers.ModelSerializer):
    """Full schedule representation — used for list and retrieve."""

    doctor_name = serializers.SerializerMethodField()
    day_of_week_display = serializers.CharField(
        source="get_day_of_week_display", read_only=True
    )

    class Meta:
        model = Schedule
        fields = [
            "id",
            "doctor_name",
            "day_of_week",
            "day_of_week_display",
            "start_time",
            "end_time",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "doctor_name", "day_of_week_display", "created_at"]

    def get_doctor_name(self, obj) -> str:
        return get_display_name(obj.doctor.user)


class ScheduleCreateSerializer(serializers.ModelSerializer):
    """Write serializer — used for create and update.

    Doctor is excluded: it is assigned automatically from request.user
    in perform_create(), so it cannot be overridden via the API body.
    """

    class Meta:
        model = Schedule
        fields = ["id", "day_of_week", "start_time", "end_time", "is_active"]
        read_only_fields = ["id"]

    def validate(self, data):
        start = data.get("start_time") or getattr(self.instance, "start_time", None)
        end = data.get("end_time") or getattr(self.instance, "end_time", None)
        if start is not None and end is not None and start >= end:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return data
