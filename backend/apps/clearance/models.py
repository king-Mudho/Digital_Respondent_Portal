"""
Official research-clearance documents (2026-09-30): the letters that prove this study is a genuine,
authorised piece of research -- not a scam -- so a respondent who opens their invitation link can check
who approved it and read the letters themselves.

Deliberately separate from apps.evidence.DocumentRecord, which is the documentary-evidence register (public
policy documents, reports etc. coded as qualitative research material, docs/14). A ClearanceDocument is
never coded, never triangulated, and is about *this study's own authorisation*, not evidence for it.

A document is shown to a respondent only when a staff member has explicitly set is_public=True -- the
default is False, so uploading one never exposes it by accident (docs/18: "only documents explicitly
marked public/respondent-visible may be accessible to respondents").
"""

from django.db import models


class ClearanceDocumentType(models.TextChoices):
    ETHICS_CLEARANCE = "ETHICS_CLEARANCE", "Research ethics clearance"
    INSTITUTIONAL_APPROVAL = "INSTITUTIONAL_APPROVAL", "Institutional / government approval"
    SUPERVISION_CONFIRMATION = "SUPERVISION_CONFIRMATION", "Confirmation of supervision"
    INTRODUCTION_LETTER = "INTRODUCTION_LETTER", "Introduction / support letter"
    OTHER = "OTHER", "Other"


class ClearanceDocument(models.Model):
    title = models.CharField(max_length=255)
    issuing_body = models.CharField(max_length=255)
    document_type = models.CharField(max_length=32, choices=ClearanceDocumentType.choices)
    # e.g. "Annex 19, Form GRSD 17 SEBS/06/2025" or "Ref J/122" -- printed on the letter itself, not invented.
    reference_number = models.CharField(max_length=128, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    # Shown to the respondent alongside the document -- a plain-language line, not the letter's own text.
    description = models.TextField(blank=True)

    # The uploaded file, stored privately -- same pattern as apps.evidence.DocumentRecord's source file.
    file_ref = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_uploaded_at = models.DateTimeField(null=True, blank=True)

    # Off by default: a document exists in the register before anyone has decided it should be shown.
    is_public = models.BooleanField(default=False)
    # For retiring a superseded letter without losing the record of it having existed (never delete outright
    # once it has been public -- docs/18 audit-trail convention).
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "issue_date", "id"]

    def __str__(self):
        return f"{self.title} ({self.issuing_body})"

    @property
    def visible_to_respondents(self) -> bool:
        return self.is_public and self.active and bool(self.file_ref)
