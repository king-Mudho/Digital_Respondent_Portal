from django.contrib import admin

from .models import ConsentRecord


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("sample_case", "consent_type", "decision", "method", "timestamp")
    list_filter = ("consent_type", "decision", "method")
    search_fields = ("sample_case__sample_id",)
