from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.throttling import LoginRateThrottle, RefreshRateThrottle
from apps.users.serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """JWT login endpoint. Returns access + refresh tokens with custom claims.

    Rate limited to 5 requests/minute per IP to prevent brute-force attacks.
    AllowAny views don't inherit the global DEFAULT_THROTTLE_CLASSES once
    throttle_classes is overridden here, so the global AnonRateThrottle is
    listed explicitly alongside LoginRateThrottle (defense in depth).
    """

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle, AnonRateThrottle]


class CustomTokenRefreshView(TokenRefreshView):
    """JWT refresh endpoint. Issues a new access + refresh token pair.

    Rate limited to prevent abuse of the refresh flow (e.g. brute-forcing
    stolen/expired refresh tokens). SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is
    True, so each call also blacklists the consumed refresh token.
    Global AnonRateThrottle is listed explicitly for the same reason as
    CustomTokenObtainPairView above.
    """

    throttle_classes = [RefreshRateThrottle, AnonRateThrottle]


class UserViewSet(viewsets.GenericViewSet):
    """ViewSet exposing only the /me/ endpoint for the authenticated user.

    No list/create/destroy — users manage their own profile only.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserUpdateSerializer
        return UserSerializer

    @extend_schema(
        summary="Get or update authenticated user profile",
        tags=["users"],
    )
    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """GET → returns profile. PATCH → updates first_name / last_name."""
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Re-serialize with the read serializer so the response carries the
        # full profile (id, email, role, …), not just the edited fields.
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)
