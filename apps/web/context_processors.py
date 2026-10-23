"""Template context for the web UI layout."""

from apps.core.roles import is_admin, is_doctor, is_patient


def roles(request):
    """Expose the shared role predicates so templates never compare roles."""
    user = getattr(request, "user", None)
    return {
        "user_is_patient": is_patient(user),
        "user_is_doctor": is_doctor(user),
        "user_is_admin": is_admin(user),
    }
