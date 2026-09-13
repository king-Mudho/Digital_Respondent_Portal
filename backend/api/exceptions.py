"""
Uniform error envelope per docs/06_API_ARCHITECTURE.md:

    { "error": { "code": "string", "message": "human readable", "field_errors": {} } }
"""

from rest_framework.views import exception_handler


def _first_message(field_errors: dict) -> str:
    """The first field error as a plain sentence. Field errors nest
    arbitrarily (a list per field, and a dict per field for nested
    serializers), so walk down to the first string."""
    for value in field_errors.values():
        while isinstance(value, dict):
            value = next(iter(value.values()), None)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is not None:
            return str(value)
    return "An error occurred."


def drp_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    field_errors = {}
    message = "An error occurred."

    if isinstance(detail, dict):
        field_errors = {k: v for k, v in detail.items() if k != "detail"}
        if "detail" in detail:
            message = detail["detail"]
        elif field_errors:
            # A DRF ValidationError has no top-level "detail" -- the useful
            # text is per field. Leaving `message` as the generic string
            # meant a caller showing only `message` (the whole respondent
            # flow, which has no field-level UI) told the user "an error
            # occurred" when the API knew exactly what was wrong.
            message = _first_message(field_errors)
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
