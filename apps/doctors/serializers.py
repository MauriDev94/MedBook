"""Serializers for the doctors app."""

from rest_framework import serializers

from apps.core.utils import get_display_name
from apps.doctors.models import Doctor, Specialty


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
