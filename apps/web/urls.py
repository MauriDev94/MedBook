from django.urls import path

from apps.web.views import HomeView

app_name = "web"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
]
