from rest_framework import status as http_status
from rest_framework.response import Response


def api_response(status_text, message, data=None, status_code=http_status.HTTP_200_OK):
    if data is None:
        data = {}
    return Response(
        {
            "status": status_text,
            "data": data,
            "message": message,
        },
        status=status_code,
    )