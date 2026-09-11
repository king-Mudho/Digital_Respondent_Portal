from apps.sampling.services import next_sequence


def generate_document_id() -> str:
    """DOC-<sequence(4)>, e.g. DOC-0042. System-generated, never user-entered,
    same DB-sequence approach as Master_ID/Sample_ID/KII_ID."""
    seq = next_sequence("DOCUMENT_ID")
    return f"DOC-{seq:04d}"
