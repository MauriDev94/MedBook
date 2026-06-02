"""Django Admin configuration for the appointments app."""

from django.contrib import admin
from django.utils.html import format_html

from apps.appointments.models import Appointment, MedicalNote, TimeSlot

_STATUS_COLORS = {
    "pending": "#f59e0b",
    "confirmed": "#10b981",
    "cancelled": "#ef4444",
    "completed": "#3b82f6",
    "no_show": "#6b7280",
}


class MedicalNoteInline(admin.StackedInline):
    model = MedicalNote
    extra = 0
    readonly_fields = ["author", "created_at"]
    fields = ["author", "content", "created_at"]


@admin.action(description="Mark selected appointments as no-show")
def mark_as_no_show(modeladmin, request, queryset):
    """Bulk action — only acts on confirmed appointments."""
    updated = queryset.filter(status=Appointment.Status.CONFIRMED).update(
        status=Appointment.Status.NO_SHOW
    )
    modeladmin.message_user(request, f"{updated} appointment(s) marked as no-show.")


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["schedule", "start_datetime", "end_datetime", "status"]
    list_filter = ["status", "start_datetime"]
    search_fields = [
        "schedule__doctor__user__last_name",
        "schedule__doctor__user__email",
    ]
    ordering = ["start_datetime"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("schedule__doctor__user")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "short_id",
        "patient_name",
        "doctor_name",
        "slot_datetime",
        "status_badge",
        "created_at",
    ]
    list_filter = ["status", "doctor__specialties", "created_at"]
    search_fields = [
        "patient__user__email",
        "patient__user__first_name",
        "patient__user__last_name",
        "doctor__user__email",
        "doctor__user__first_name",
        "doctor__user__last_name",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    inlines = [MedicalNoteInline]
    actions = [mark_as_no_show]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("patient__user", "doctor__user", "slot__schedule")
        )

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8]

    @admin.display(description="Patient", ordering="patient__user__last_name")
    def patient_name(self, obj):
        return obj.patient.user.full_name or obj.patient.user.email

    @admin.display(description="Doctor", ordering="doctor__user__last_name")
    def doctor_name(self, obj):
        return obj.doctor.user.full_name or obj.doctor.user.email

    @admin.display(description="Slot", ordering="slot__start_datetime")
    def slot_datetime(self, obj):
        return obj.slot.start_datetime.strftime("%Y-%m-%d %H:%M")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        color = _STATUS_COLORS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:bold">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(MedicalNote)
class MedicalNoteAdmin(admin.ModelAdmin):
    list_display = ["appointment", "author", "created_at"]
    search_fields = ["appointment__id", "author__email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("appointment", "author")
