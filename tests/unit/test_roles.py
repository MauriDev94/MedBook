"""Role predicates shared by DRF permission classes and web mixins (ADR 0002).

Both RBAC paths ask these functions, so "is this user a patient?" cannot
drift between the API and the web UI.
"""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.core.roles import is_admin, is_doctor, is_patient
from apps.users.models import Role
from tests.factories import UserFactory

PREDICATES = {Role.PATIENT: is_patient, Role.DOCTOR: is_doctor, Role.ADMIN: is_admin}


@pytest.mark.django_db
@pytest.mark.parametrize("role", list(PREDICATES))
class TestRolePredicates:
    def test_true_for_own_role(self, role):
        user = UserFactory(role=role)

        assert PREDICATES[role](user) is True

    def test_false_for_other_roles(self, role):
        predicate = PREDICATES[role]

        for other in set(PREDICATES) - {role}:
            assert predicate(UserFactory(role=other)) is False

    def test_false_for_anonymous_user(self, role):
        assert PREDICATES[role](AnonymousUser()) is False

    def test_false_without_user(self, role):
        assert PREDICATES[role](None) is False
