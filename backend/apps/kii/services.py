from apps.sampling.services import next_sequence

from .models import KIIRecord


def generate_kii_id() -> str:
    """KII-<sequence(4)>, e.g. KII-0042. System-generated, never user-entered,
    same DB-sequence approach as Master_ID/Sample_ID
    (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md)."""
    seq = next_sequence("KII_ID")
    return f"KII-{seq:04d}"


def create_kii_record(**fields) -> KIIRecord:
    record = KIIRecord(kii_id=generate_kii_id(), **fields)
    record.full_clean()
    record.save()
    return record
