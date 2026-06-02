"""Custom DRF exception handler.

All API errors are normalised to a single shape:

    {
        "detail":      "<human-readable message>",
        "code":        "<machine-readable code>",
        "field_errors": { "field": ["msg"] }   # only on validation errors
    }

This makes frontend error handling trivial — one shape, always.
"""

from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Normalise every DRF exception to a consistent response shape."""
    response = exception_handler(exc, context)

    if response is None:
        # Non-DRF exception (e.g. ValueError) — let Django handle it
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
