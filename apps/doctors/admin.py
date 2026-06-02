"""Django Admin configuration for the doctors app."""

from django.contrib import admin

from apps.doctors.models import Doctor, Schedule, Specialty


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0
    fields = ["day_of_week", "start_time", "end_time", "is_active"]
    ordering = ["day_of_week", "start_time"]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "license_number", "consultation_duration"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "license_number",
    ]
    filter_horizontal = ["specialties"]
    inlines = [ScheduleInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="Full name", ordering="user__last_name")
    def full_name(self, obj):
        return obj.user.full_name or obj.user.email

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["doctor", "day_of_week", "start_time", "end_time", "is_active"]
    list_filter = ["day_of_week", "is_active"]
    search_fields = ["doctor__user__email", "doctor__user__last_name"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("doctor__user")
