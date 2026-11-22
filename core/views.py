from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from core.responses import api_response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    try:
        connection.ensure_connection()
        db_status = "connected"
    except Exception as e:
        return api_response(
            status_text="error",
            message=f"Database connection failed: {str(e)}",
            data={},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return api_response(
        status_text="success",
        message="Server and PostgreSQL database are up and running.",
        data={
            "project": "Meeting Room Allocation System (BacBon)",
            "database": db_status,
        },
        status_code=status.HTTP_200_OK,
    )