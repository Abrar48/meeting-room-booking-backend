from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler


class InvalidTimeRangeError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid or past time range provided."
    default_code = "invalid_time_range"


class BookingConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The requested time slot overlaps with an existing confirmed booking."
    default_code = "booking_conflict"


ERROR_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "Validation failed.",
    status.HTTP_401_UNAUTHORIZED: (
        "Authentication credentials were not provided or are invalid."
    ),
    status.HTTP_403_FORBIDDEN: (
        "You do not have permission to perform this action."
    ),
    status.HTTP_404_NOT_FOUND: "Resource not found.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "Method not allowed.",
    status.HTTP_409_CONFLICT: "Booking schedule conflict.",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "Unsupported media type.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests.",
}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    error_data = response.data

    message = ERROR_MESSAGES.get(
        response.status_code,
        "Request failed.",
    )

    if isinstance(error_data, dict) and "detail" in error_data:
        message = str(error_data["detail"])

    if isinstance(exc, ValidationError):
        message = "Validation failed."

    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        message = ERROR_MESSAGES[status.HTTP_401_UNAUTHORIZED]
        error_data = {}

    elif isinstance(exc, PermissionDenied):
        message = ERROR_MESSAGES[status.HTTP_403_FORBIDDEN]
        error_data = {}

    if isinstance(error_data, list):
        error_data = {"errors": error_data}

    elif not isinstance(error_data, dict):
        error_data = {"detail": str(error_data)}

    response.data = {
        "status": "error",
        "data": error_data,
        "message": message,
    }

    return response