"""Serializers for the appointments app.

One serializer per action — shapes diverge between create, list, and detail.
Business validation is delegated to services.py, not duplicated here.
"""

from rest_framework import serializers

from apps.appointments.models import Appointment, TimeSlot


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

    Validates slot availability and patient conflict via the service layer.
    Sets patient and doctor automatically from context — never from request body.
    """

    class Meta:
        model = Appointment
        fields = ["slot", "reason"]

    def validate_slot(self, slot: TimeSlot) -> TimeSlot:
        """Field-level: slot must be AVAILABLE."""
        if slot.status != TimeSlot.Status.AVAILABLE:
            raise serializers.ValidationError("This time slot is no longer available.")
        return slot

    def validate(self, data: dict) -> dict:
        """Cross-field: check patient has no overlapping appointment."""
        from apps.appointments.services import validate_appointment_booking

        request = self.context["request"]
        patient = request.user.patient_profile
        validate_appointment_booking(patient=patient, slot=data["slot"])
        return data

    def create(self, validated_data: dict) -> Appointment:
        request = self.context["request"]
        patient = request.user.patient_profile
        doctor = validated_data["slot"].schedule.doctor

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            slot=validated_data["slot"],
            reason=validated_data.get("reason", ""),
        )
        # Reserve the slot atomically with the appointment creation
        appointment.slot.status = TimeSlot.Status.RESERVED
        appointment.slot.save(update_fields=["status", "updated_at"])
        return appointment


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
        return obj.patient.user.full_name or obj.patient.user.email

    def get_doctor_name(self, obj) -> str:
        return obj.doctor.user.full_name or obj.doctor.user.email


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
        return obj.patient.user.full_name or obj.patient.user.email

    def get_doctor_name(self, obj) -> str:
        return obj.doctor.user.full_name or obj.doctor.user.email

    def get_can_cancel(self, obj) -> bool:
        return obj.can_be_cancelled()


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """Partial update — only the reason field is editable after booking."""

    class Meta:
        model = Appointment
        fields = ["reason"]
