"""URL configuration for MedBook project."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.appointments.views import AppointmentViewSet
from apps.doctors.views import DoctorViewSet, SpecialtyViewSet
from apps.users.views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("doctors", DoctorViewSet, basename="doctor")
router.register("specialties", SpecialtyViewSet, basename="specialty")

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # API router — appointments, doctors, specialties
    path("api/", include(router.urls)),
    # User / Auth endpoints
    path("api/", include("apps.users.urls")),
]
