from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.users.serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """JWT login endpoint. Returns access + refresh tokens with custom claims."""

    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.GenericViewSet):
    """ViewSet exposing only the /me/ endpoint for the authenticated user.

    No list/create/destroy — users manage their own profile only.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserUpdateSerializer
        return UserSerializer

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """GET → returns profile. PATCH → updates first_name / last_name."""
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
