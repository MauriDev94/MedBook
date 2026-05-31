from django.contrib import admin

from apps.appointments.models import Appointment, MedicalNote, TimeSlot


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["schedule", "start_datetime", "end_datetime", "status"]
    list_filter = ["status", "start_datetime"]
    search_fields = [
        "schedule__doctor__user__last_name",
        "schedule__doctor__user__email",
    ]
    ordering = ["start_datetime"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["patient", "doctor", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["patient__user__email", "doctor__user__email"]
    ordering = ["-created_at"]


@admin.register(MedicalNote)
class MedicalNoteAdmin(admin.ModelAdmin):
    list_display = ["appointment", "author", "created_at"]
    search_fields = ["appointment__id", "author__email"]
    ordering = ["-created_at"]
