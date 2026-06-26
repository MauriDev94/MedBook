from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from apps.users.views import CustomTokenObtainPairView, CustomTokenRefreshView

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
]
