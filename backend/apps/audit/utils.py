from apps.audit.middleware import get_current_user
from apps.audit.models import AuditEvent


def log_action(action: str, obj, metadata: dict | None = None, *, user=None):
    """Record a sensitive action per docs/18_DATA_PRIVACY_AND_COMPLIANCE.md:
    invitation issuance/revocation, consent change, QA decision, reserve
    activation, data lock -- and, per docs/09_IDENTIFIER_AND_SAMPLING_
    CONTROL.md, a rejected invalid S00-S16 workflow transition attempt.

    `user` lets a caller that already knows who acted (a Celery task with no
    request, a bulk operation, an export) attribute the event directly,
    instead of relying solely on get_current_user()'s request-bound
    thread-local -- which is empty outside a request/response cycle (a
    background task) and, for a streamed response, can already have been
    cleared by the time a generator body runs. Accepts a User instance, a
    raw pk, or None (falls back to get_current_user()).
    """
    if user is None:
        user = get_current_user()
    kwargs = {"user_id": user} if isinstance(user, int) else {"user": user}
    AuditEvent.objects.create(
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
        metadata=metadata or {},
        **kwargs,
    )
