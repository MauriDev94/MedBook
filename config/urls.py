"""URL configuration for MedBook project."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.appointments.views import AppointmentViewSet, MedicalNoteViewSet
from apps.core.views import health_check
from apps.doctors.views import DoctorViewSet, ScheduleViewSet, SpecialtyViewSet
from apps.users.views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("doctors", DoctorViewSet, basename="doctor")
router.register("schedules", ScheduleViewSet, basename="schedule")
router.register("specialties", SpecialtyViewSet, basename="specialty")

# Nested routes — medical notes live under their appointment
notes_list = MedicalNoteViewSet.as_view({"get": "list", "post": "create"})
notes_detail = MedicalNoteViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    # Root → Swagger docs (public deployment URL lands on interactive docs, not 404)
    path("", RedirectView.as_view(url="/api/docs/", permanent=False), name="root"),
    # Infrastructure
    path("health/", health_check, name="health-check"),
    # Admin
    path("admin/", admin.site.urls),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # API router — appointments, doctors, schedules, specialties, users
    path("api/", include(router.urls)),
    # Nested: /api/appointments/{appointment_pk}/notes/
    path(
        "api/appointments/<uuid:appointment_pk>/notes/",
        notes_list,
        name="appointment-notes-list",
    ),
    path(
        "api/appointments/<uuid:appointment_pk>/notes/<uuid:pk>/",
        notes_detail,
        name="appointment-notes-detail",
    ),
    # User / Auth endpoints
    path("api/", include("apps.users.urls")),
]
