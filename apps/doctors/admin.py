from django.contrib import admin

from apps.doctors.models import Doctor, Schedule, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["__str__", "license_number", "consultation_duration"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "license_number",
    ]
    filter_horizontal = ["specialties"]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["doctor", "day_of_week", "start_time", "end_time", "is_active"]
    list_filter = ["day_of_week", "is_active"]
    search_fields = ["doctor__user__email", "doctor__user__last_name"]
