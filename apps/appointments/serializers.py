"""Serializers for the appointments app.

One serializer per action — shapes diverge between create, list, and detail.
Business validation is fully delegated to services.py — not duplicated here.
"""

from rest_framework import serializers

from apps.appointments.models import Appointment, MedicalNote, TimeSlot
from apps.core.utils import get_display_name


class TimeSlotSerializer(serializers.ModelSerializer):
    """Read-only representation of a time slot."""

    doctor_id = serializers.UUIDField(source="schedule.doctor.id", read_only=True)

    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "doctor_id",
            "start_datetime",
            "end_datetime",
            "status",
        ]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Write serializer for booking a new appointment.

    All business validation (slot availability, overlap check) is delegated
    to services.validate_appointment_booking() — no duplication here.
    The actual creation (including atomic slot reservation) is handled by
    services.create_appointment().
    """

    class Meta:
        model = Appointment
        fields = ["slot", "reason"]

    def validate(self, data: dict) -> dict:
        """Delegate all cross-field validation to the service layer."""
        from apps.appointments.services import validate_appointment_booking

        request = self.context["request"]
        patient = request.user.patient_profile
        validate_appointment_booking(patient=patient, slot=data["slot"])
        return data

    def create(self, validated_data: dict) -> Appointment:
        """Delegate atomic creation (appointment + slot reservation) to service."""
        from apps.appointments.services import create_appointment

        request = self.context["request"]
        patient = request.user.patient_profile
        doctor = validated_data["slot"].schedule.doctor
        return create_appointment(
            patient=patient,
            doctor=doctor,
            slot=validated_data["slot"],
            reason=validated_data.get("reason", ""),
        )


class AppointmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    slot_start = serializers.DateTimeField(source="slot.start_datetime", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_name",
            "doctor_name",
            "slot_start",
            "status",
        ]

    def get_patient_name(self, obj) -> str:
        return get_display_name(obj.patient.user)

    def get_doctor_name(self, obj) -> str:
        return get_display_name(obj.doctor.user)


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Full representation for retrieve views."""

    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    slot = TimeSlotSerializer(read_only=True)
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_name",
            "doctor_name",
            "slot",
            "reason",
            "status",
            "can_cancel",
            "created_at",
            "updated_at",
        ]

    def get_patient_name(self, obj) -> str:
        return get_display_name(obj.patient.user)

    def get_doctor_name(self, obj) -> str:
        return get_display_name(obj.doctor.user)

    def get_can_cancel(self, obj) -> bool:
        return obj.can_be_cancelled()


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """Partial update — only the reason field is editable after booking."""

    class Meta:
        model = Appointment
        fields = ["reason"]


class MedicalNoteSerializer(serializers.ModelSerializer):
    """Read/write serializer for medical notes.

    author and appointment are excluded from the writable fields —
    both are injected in perform_create() from the URL and request context.
    """

    author_name = serializers.SerializerMethodField()

    class Meta:
        model = MedicalNote
        fields = ["id", "content", "author_name", "created_at"]
        read_only_fields = ["id", "author_name", "created_at"]

    def get_author_name(self, obj) -> str:
        return get_display_name(obj.author)
