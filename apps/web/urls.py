from django.urls import path

from apps.web.views import (
    DoctorDetailView,
    DoctorListView,
    HomeView,
    PanelView,
    SignupView,
    WebLoginView,
    WebLogoutView,
)

app_name = "web"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", WebLoginView.as_view(), name="login"),
    path("logout/", WebLogoutView.as_view(), name="logout"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("panel/", PanelView.as_view(), name="panel"),
    path("doctors/", DoctorListView.as_view(), name="doctor_list"),
    path("doctors/<uuid:pk>/", DoctorDetailView.as_view(), name="doctor_detail"),
]
