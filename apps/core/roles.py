"""Role predicates shared by both RBAC paths (ADR 0002).

The API's DRF permission classes (apps.core.permissions) and the web UI's
view mixins (apps.web.mixins) both ask these functions, so "is this user a
patient?" cannot drift between the two.
"""

from apps.users.models import Role


def is_patient(user) -> bool:
    return _has_role(user, Role.PATIENT)


def is_doctor(user) -> bool:
    return _has_role(user, Role.DOCTOR)


def is_admin(user) -> bool:
    return _has_role(user, Role.ADMIN)


def _has_role(user, role: Role) -> bool:
    # is_authenticated first: AnonymousUser has no `role` attribute.
    return bool(user and user.is_authenticated and user.role == role)
