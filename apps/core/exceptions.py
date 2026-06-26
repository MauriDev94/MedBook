"""Custom DRF exception handler.

All API errors are normalised to a single shape:

    {
        "detail":      "<human-readable message>",
        "code":        "<machine-readable code>",
        "field_errors": { "field": ["msg"] }   # only on validation errors
    }

This makes frontend error handling trivial — one shape, always.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class SlotConflict(APIException):
    """Raised when a TimeSlot is taken by a concurrent request (real race).

    Distinct from the pre-check ValidationError raised by
    validate_appointment_booking() (→ 400): this is the atomic UPDATE
    losing the race inside create_appointment() — a genuine conflict,
    so it maps to 409 rather than 400.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This time slot is no longer available."
    default_code = "slot_conflict"


def custom_exception_handler(exc, context):
    """Normalise every DRF exception to a consistent response shape."""
    response = exception_handler(exc, context)

    if response is None:
        # DRF doesn't handle Django's ValidationError. Services raise it
        # (e.g. when losing the atomic slot-reservation race inside
        # serializer.create()), where it escapes run_validation and would
        # otherwise surface as a 500. Map it to a 400 with the standard shape.
        if isinstance(exc, DjangoValidationError):
            return _handle_django_validation_error(exc)
        from apps.appointments.models import InvalidTransition

        if isinstance(exc, InvalidTransition):
            return _handle_django_validation_error(exc)
        # Any other non-DRF exception (e.g. ValueError) — let Django handle it
        return None

    code = getattr(exc, "default_code", "error")
    data = {"code": code}

    if isinstance(exc, ValidationError):
        data["code"] = "validation_error"
        _handle_validation_error(exc, response, data)
    else:
        # NotFound, PermissionDenied, AuthenticationFailed, etc.
        raw_detail = response.data.get("detail", str(exc))
        data["detail"] = str(raw_detail)

    response.data = data
    return response


def _handle_django_validation_error(exc):
    """Map a django.core.exceptions.ValidationError to a 400 Response.

    Mirrors the {detail, code} shape used for DRF validation errors.
    Django's ValidationError exposes its messages via the `messages` list.
    """
    messages = getattr(exc, "messages", None) or [str(exc)]
    return Response(
        {"detail": str(messages[0]), "code": "validation_error"},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _handle_validation_error(exc, response, data):
    """Parse ValidationError into detail + optional field_errors."""
    raw = response.data

    if isinstance(raw, dict):
        non_field = raw.pop("non_field_errors", None)

        if non_field:
            # Raised via validate() with a plain message
            data["detail"] = str(non_field[0]) if non_field else "Invalid input."
        elif "detail" in raw and len(raw) == 1:
            # raise ValidationError("plain message") in a view
            data["detail"] = str(raw["detail"])
        else:
            # Field-level errors: {"email": [...], "slot": [...]}
            data["detail"] = "Invalid input."
            data["field_errors"] = {
                field: [str(e) for e in errors]
                if isinstance(errors, list)
                else [str(errors)]
                for field, errors in raw.items()
            }
    elif isinstance(raw, list):
        # raise ValidationError(["msg1", "msg2"])
        data["detail"] = str(raw[0]) if raw else "Invalid input."
    else:
        data["detail"] = str(raw)
