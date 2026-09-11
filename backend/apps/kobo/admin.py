from django.contrib import admin

from .models import QUANSubmission, ReconciliationLog


@admin.register(QUANSubmission)
class QUANSubmissionAdmin(admin.ModelAdmin):
    list_display = ("kobo_submission_uuid", "sample_case", "administration_mode", "qa_status", "submitted_at", "last_edited_at")
    list_filter = ("administration_mode", "qa_status")
    search_fields = ("kobo_submission_uuid", "sample_case__sample_id")
    readonly_fields = ("kobo_submission_uuid", "payload_content_hash", "raw_payload_ref")


@admin.register(ReconciliationLog)
class ReconciliationLogAdmin(admin.ModelAdmin):
    list_display = ("run_started_at", "triggered_by", "submissions_pulled", "new_submissions", "updated_submissions", "mismatches_flagged")
    list_filter = ("triggered_by",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
