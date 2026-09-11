"""
Uniform error envelope per docs/06_API_ARCHITECTURE.md:

    { "error": { "code": "string", "message": "human readable", "field_errors": {} } }
"""

from rest_framework.views import exception_handler


def drp_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    field_errors = {}
    message = "An error occurred."

    if isinstance(detail, dict):
        message = detail.get("detail", message)
        field_errors = {k: v for k, v in detail.items() if k != "detail"}
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    response.data = {
        "error": {
            "code": getattr(exc, "default_code", exc.__class__.__name__),
            "message": str(message),
            "field_errors": field_errors,
        }
    }
    return response
