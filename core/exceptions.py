from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)
from rest_framework.views import exception_handler

from core.responses import api_response


class InvalidTimeRangeError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid or past time range provided."
    default_code = "invalid_time_range"


class BookingConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The requested time slot overlaps with an existing confirmed booking."
    default_code = "booking_conflict"


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            return api_response(
                status_text="error",
                message="Authentication credentials were not provided or are invalid.",
                data={},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if isinstance(exc, PermissionDenied):
            return api_response(
                status_text="error",
                message="You do not have permission to perform this action.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        message = "Request failed."
        if isinstance(response.data, dict) and "detail" in response.data:
            message = str(response.data["detail"])

        return api_response(
            status_text="error",
            message=message,
            data=response.data if isinstance(response.data, dict) else {},
            status_code=response.status_code,
        )

    return response