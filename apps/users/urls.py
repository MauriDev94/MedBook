from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.users.views import CustomTokenObtainPairView

urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
]
