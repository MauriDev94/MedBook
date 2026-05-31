"""Shared utility functions for the MedBook project."""


def get_display_name(user) -> str:
    """Return user's full name, or email as fallback.

    Used across models and serializers wherever a human-readable name
    is needed. Centralizes the pattern: obj.full_name or obj.email.
    """
    return user.full_name or user.email
