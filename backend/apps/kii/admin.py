from django.contrib import admin

from .models import KIIRecord


@admin.register(KIIRecord)
class KIIRecordAdmin(admin.ModelAdmin):
    list_display = ("kii_id", "participant_name", "stakeholder_category", "status", "transcript_status")
    list_filter = ("status", "transcript_status", "coding_status")
    search_fields = ("kii_id", "participant_name")
    readonly_fields = ("kii_id",)
