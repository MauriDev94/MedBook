from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Custom DRF exception handler that standardises error responses."""
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "error": response.status_text,
            "detail": response.data,
        }

    return response
