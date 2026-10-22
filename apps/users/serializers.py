from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds custom claims (role, email, full_name) to the JWT payload.

    Security note: JWT payloads are base64-encoded, NOT encrypted. Anyone in
    possession of the token (e.g. via browser devtools, a proxy, or a stolen
    token) can read these claims without verifying the signature. Therefore
    only non-sensitive data is placed here. ``role``, ``email`` and
    ``full_name`` are considered safe to expose this way — this is a
    deliberate design decision, not an oversight. Do NOT add sensitive data
    (passwords, secrets, PII beyond what's already public-facing, etc.) to
    these claims.
    """

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


class PatientRegistrationSerializer(serializers.Serializer):
    """Write serializer — used for POST /api/users/register/.

    Field-level checks (format, length, required) live here; the business
    rules (unique email, password policy) and the creation itself are
    delegated to apps.users.services. There is no `role` field: the service
    always creates a patient, so privilege escalation is impossible. The view
    responds with UserSerializer, never with this serializer.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    emergency_contact = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )

    def validate(self, data: dict) -> dict:
        """Delegate cross-field business validation to the service layer."""
        from apps.users.services import validate_patient_registration

        validate_patient_registration(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
        )
        return data

    def create(self, validated_data: dict) -> User:
        """Delegate atomic creation (User + Patient profile) to the service."""
        from apps.users.services import register_patient

        return register_patient(**validated_data)


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
