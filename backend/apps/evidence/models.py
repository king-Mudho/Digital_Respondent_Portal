"""
DocumentRecord model. Pulled forward from Phase 7 (docs/27_AGENT_EXECUTION_
PLAN.md) because qa.QAEvent (Phase 4) has a nullable FK to it
(docs/05_DATABASE_ARCHITECTURE.md). Full field set per docs/05 and
docs/14_DOCUMENTARY_EVIDENCE_MODULE.md; the frontend/workflow wiring itself
still lands in Phase 7.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models


class DocumentType(models.TextChoices):
    OFFICIAL = "OFFICIAL", "Official"
    SECONDARY = "SECONDARY", "Secondary"
    PLATFORM = "PLATFORM", "Platform"


class AuthenticityAssessment(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"
    DISPUTED = "DISPUTED", "Disputed"


class DocumentQAStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    INCLUDED = "INCLUDED", "Included"
    EXCLUDED = "EXCLUDED", "Excluded"


class DocumentRecord(models.Model):
    """A provenance-controlled evidence repository, not a general file dump
    (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md). construct_tags may reference
    ABI dimensions as relevance tags only -- never a score
    (AGENTS.md ground rule 3, docs/25_FUTURE_ABI_ENGINE_PHASE4.md)."""

    document_id = models.CharField(max_length=32, unique=True, editable=False)
    organisation = models.ForeignKey(
        "sampling.Organisation", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="document_records",
    )
    title = models.CharField(max_length=512)
    author_or_speaker = models.CharField(max_length=255, blank=True)
    publication_or_event_date = models.DateField(null=True, blank=True)
    source_url_or_reference = models.CharField(max_length=1024, blank=True)
    document_type = models.CharField(max_length=16, choices=DocumentType.choices)
    authenticity_assessment = models.CharField(
        max_length=16, choices=AuthenticityAssessment.choices, default=AuthenticityAssessment.UNVERIFIED
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    geographic_scope = models.CharField(max_length=255, blank=True)
    # Widened 2026-09-12: the real Documentary Evidence register's "Value
    # chain" values can exceed 32 chars (e.g. "Grains, oilseeds & milling").
    value_chain = models.CharField(max_length=255, blank=True)
    # NFM, BANK, DGR, AGC, INS, FST + ABI-dimension relevance tags -- tags
    # only, never a score (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md).
    construct_tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    evidence_extract = models.TextField(blank=True)
    interpretive_memo = models.TextField(blank=True)
    # Losslessly preserves register-provenance fields with no dedicated
    # model field (register row number, thematic Block, Link/Status
    # retrieval notes) -- nothing invented, nothing discarded. Same pattern
    # as sampling.Organisation.metadata / kii.KIIRecord.metadata.
    metadata = models.JSONField(default=dict, blank=True)
    triangulation_quan_submissions = models.ManyToManyField(
        "kobo.QUANSubmission", blank=True, related_name="triangulated_documents"
    )
    triangulation_kii_records = models.ManyToManyField(
        "kii.KIIRecord", blank=True, related_name="triangulated_documents"
    )
    reviewer = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_documents",
    )
    qa_status = models.CharField(max_length=16, choices=DocumentQAStatus.choices, default=DocumentQAStatus.PENDING)
    # The uploaded source file itself (screenshot, scan, recording), stored
    # privately under PRIVATE_DATA_ROOT/documents/ -- never a web-served
    # path, downloaded only through the permission-checked, audited
    # DocumentFileView. source_file_ref is the path relative to
    # PRIVATE_DATA_ROOT; the other fields are display/download metadata.
    source_file_ref = models.CharField(max_length=255, blank=True)
    source_file_name = models.CharField(max_length=255, blank=True)
    source_file_content_type = models.CharField(max_length=100, blank=True)
    source_file_size = models.PositiveIntegerField(null=True, blank=True)
    source_file_uploaded_at = models.DateTimeField(null=True, blank=True)
    # AI-assisted coding draft (apps/evidence/ai_coding.py) -- an editable
    # proposal, never itself a submission. ai_draft holds the same shape
    # kobo_submit.py consumes (field path -> value; the Section J repeat
    # group as a list of dicts). Cleared of meaning once kobo_submitted_at
    # is set, but kept as a record of what was actually submitted.
    ai_draft = models.JSONField(default=dict, blank=True)
    ai_draft_generated_at = models.DateTimeField(null=True, blank=True)
    ai_draft_model = models.CharField(max_length=64, blank=True)
    # Set only by a Documentary RA's explicit "Submit to KoboToolbox" click
    # on the reviewed draft (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md) --
    # never by ai_coding.py itself. kobo_submission_uuid is the instance's
    # meta/instanceID, useful for tracing this exact submission in Kobo.
    kobo_submission_uuid = models.CharField(max_length=64, blank=True)
    kobo_submitted_at = models.DateTimeField(null=True, blank=True)
    kobo_submitted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document_id} — {self.title}"
