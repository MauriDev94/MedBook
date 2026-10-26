import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

# Lazy: the web form shows it in the visitor's language; the API resolves
# it while English is active (apps.core.middleware.EnglishApiMiddleware).
# The admin shows it when unique_user_email_ci rejects an email.
DUPLICATE_EMAIL_MESSAGE = _("A user with this email already exists.")


class Role(models.TextChoices):
    """User roles for RBAC across the system."""

    ADMIN = "admin", "Admin"
    DOCTOR = "doctor", "Doctor"
    PATIENT = "patient", "Patient"


class UserManager(BaseUserManager):
    """Custom manager that uses email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with staff and superuser flags."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        """Find the user logging in, whatever the case of the email.

        ModelBackend calls this for the web login, the admin and the API's
        token endpoint. unique_user_email_ci allows at most one match.
        """
        return self.get(email__iexact=email)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email as the unique identifier.

    Supports three roles: admin, doctor, and patient. This model is
    created BEFORE any other model migration to satisfy Django's
    AUTH_USER_MODEL requirement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            # unique=True compares exact strings; this makes Ana@… and ana@…
            # one account. The email itself is stored as typed.
            models.UniqueConstraint(
                Lower("email"),
                name="unique_user_email_ci",
                violation_error_message=DUPLICATE_EMAIL_MESSAGE,
            ),
        ]

    @property
    def full_name(self) -> str:
        """Return the full name, or empty string if neither name is set."""
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return self.email
