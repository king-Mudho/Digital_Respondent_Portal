import threading

_local = threading.local()


class AuditContextMiddleware:
    """Stashes the current request in thread-local storage so
    apps.audit.utils.log_action() can attribute an AuditEvent without every
    call site having to pass the request through.

    Stores the request itself, not request.user, and reads .user lazily in
    get_current_user(). This app authenticates via DRF's JWTAuthentication,
    which runs inside view dispatch -- i.e. during self.get_response(request)
    below -- not in Django's AuthenticationMiddleware (which only resolves
    session auth and would leave request.user as AnonymousUser here). Reading
    request.user eagerly at __call__ entry, before dispatch has run,
    captured that pre-auth AnonymousUser every time, so every AuditEvent was
    attributed to "system" regardless of who was actually signed in. DRF's
    Request.user setter propagates the authenticated user back onto this
    same underlying request object once perform_authentication() runs, so a
    lazy read here (from inside a view/service's log_action() call, which
    only happens during get_response()) sees the real user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            response = self.get_response(request)
        finally:
            _local.request = None
        return response


def get_current_user():
    request = getattr(_local, "request", None)
    if request is None:
        return None
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None
