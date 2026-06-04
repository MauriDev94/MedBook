from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds custom claims (role, email, full_name) to the JWT payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.full_name
        return token


class UserSerializer(serializers.ModelSerializer):
    """Read-only profile serializer — used for GET /api/users/me/."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "full_name",
            "first_name",
            "last_name",
            "created_at",
        ]
        read_only_fields = ["id", "email", "role", "created_at"]

    def get_full_name(self, obj) -> str:
        return obj.full_name


class UserUpdateSerializer(serializers.ModelSerializer):
    """Write serializer — used for PATCH /api/users/me/.

    Exposes ONLY the editable fields. Email and role are not even part of the
    schema, so privilege escalation is structurally impossible. The view
    re-serializes the saved instance with UserSerializer to return the full
    profile in the response.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name"]
