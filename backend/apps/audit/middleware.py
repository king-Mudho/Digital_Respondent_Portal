import threading

_local = threading.local()


class AuditContextMiddleware:
    """Stashes the current request's user in thread-local storage so
    apps.audit.utils.log_action() can attribute an AuditEvent without every
    call site having to pass the request through.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.user = getattr(request, "user", None)
        try:
            response = self.get_response(request)
        finally:
            _local.user = None
        return response


def get_current_user():
    user = getattr(_local, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None
