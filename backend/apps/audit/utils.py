from apps.audit.middleware import get_current_user
from apps.audit.models import AuditEvent


def log_action(action: str, obj, metadata: dict | None = None):
    """Record a sensitive action per docs/18_DATA_PRIVACY_AND_COMPLIANCE.md:
    invitation issuance/revocation, consent change, QA decision, reserve
    activation, data lock -- and, per docs/09_IDENTIFIER_AND_SAMPLING_
    CONTROL.md, a rejected invalid S00-S16 workflow transition attempt.
    """
    AuditEvent.objects.create(
        user=get_current_user(),
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
        metadata=metadata or {},
    )
