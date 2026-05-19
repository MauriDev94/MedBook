from rest_framework_simplejwt.views import TokenObtainPairView

from apps.users.serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """JWT login endpoint. Returns access + refresh tokens with custom claims."""

    serializer_class = CustomTokenObtainPairSerializer
