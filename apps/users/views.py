from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.throttling import (
    LoginRateThrottle,
    RefreshRateThrottle,
    RegisterRateThrottle,
)
from apps.users.serializers import (
    CustomTokenObtainPairSerializer,
    PatientRegistrationSerializer,
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
    """ViewSet exposing /me/ for the authenticated user and public /register/.

    No list/create/destroy — users manage their own profile only, and the
    only self-service account creation is patient registration.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "register":
            return PatientRegistrationSerializer
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

    @extend_schema(
        summary="Register a new patient account",
        description=(
            "Public endpoint. Always creates a patient (any `role` sent is "
            "ignored). Returns the profile only — log in afterwards through "
            "`/api/v1/token/` to get tokens."
        ),
        tags=["auth"],
        request=PatientRegistrationSerializer,
        responses={201: UserSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="register",
        permission_classes=[AllowAny],
        # Public endpoint: a stale/invalid Bearer header must not turn a
        # sign-up into a 401, and skipping auth keeps the throttle IP-based.
        authentication_classes=[],
        throttle_classes=[RegisterRateThrottle, AnonRateThrottle],
    )
    def register(self, request):
        """POST → creates User(role=patient) + Patient profile, returns 201."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
