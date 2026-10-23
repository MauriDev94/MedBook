"""Unit tests for minor security hardening (issue #87).

Covers:
- S5: UserAttributeSimilarityValidator rejects passwords too close to
  user attributes (email, first/last name).
- S6: the admin URL is sourced from DJANGO_ADMIN_URL and always
  normalised to end with a trailing slash.
"""

import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from tests.factories import UserFactory, random_password


@pytest.mark.django_db
class TestUserAttributeSimilarityValidator:
    def test_password_similar_to_email_is_rejected(self):
        user = UserFactory(email="janedoe@medbook.com")

        with pytest.raises(ValidationError):
            validate_password(user.email, user=user)

    def test_password_similar_to_name_is_rejected(self):
        user = UserFactory(first_name="Jonathan", last_name="Smithson")

        with pytest.raises(ValidationError):
            validate_password(f"{user.first_name.lower()}123", user=user)

    def test_unrelated_strong_password_is_accepted(self):
        user = UserFactory(email="janedoe@medbook.com")

        # Should not raise — unrelated to any user attribute.
        validate_password(random_password(), user=user)


class TestAdminUrlConfig:
    def test_admin_url_setting_defaults_to_admin_slash(self, settings):
        assert settings.DJANGO_ADMIN_URL == "admin/"

    def test_admin_url_setting_always_ends_with_slash(self, settings):
        assert settings.DJANGO_ADMIN_URL.endswith("/")
