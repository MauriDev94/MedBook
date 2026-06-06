"""Tests for the ensure_superuser management command.

The command is idempotent:
- Creates superuser if none exists and env vars are set
- Skips silently if a superuser already exists
- Skips silently if env vars are not configured
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.users.models import User, Role


@pytest.mark.django_db
class TestEnsureSuperuserCommand:
    def _call(self, email="", password=""):
        out = StringIO()
        env_vars = {}
        if email:
            env_vars["DJANGO_SUPERUSER_EMAIL"] = email
        if password:
            env_vars["DJANGO_SUPERUSER_PASSWORD"] = password
        with patch.dict("os.environ", env_vars, clear=False):
            call_command("ensure_superuser", stdout=out)
        return out.getvalue()

    def test_creates_superuser_when_env_vars_set(self):
        output = self._call(email="admin@medbook.com", password="Admin1234!")

        user = User.objects.get(email="admin@medbook.com")
        assert user.is_superuser is True
        assert user.role == Role.ADMIN
        assert "created" in output

    def test_skips_if_superuser_already_exists(self):
        # Create a superuser first
        User.objects.create_superuser(
            email="existing@medbook.com",
            password="Admin1234!",
            role=Role.ADMIN,
        )

        output = self._call(email="new@medbook.com", password="Admin1234!")

        assert not User.objects.filter(email="new@medbook.com").exists()
        assert "already exists" in output

    def test_skips_if_email_not_set(self):
        output = self._call(password="Admin1234!")  # no email

        assert not User.objects.filter(is_superuser=True).exists()
        assert "not set" in output

    def test_skips_if_password_not_set(self):
        output = self._call(email="admin@medbook.com")  # no password

        assert not User.objects.filter(email="admin@medbook.com").exists()
        assert "not set" in output
