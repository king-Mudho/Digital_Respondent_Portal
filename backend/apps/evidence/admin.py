from django.contrib import admin

from .models import DocumentRecord


@admin.register(DocumentRecord)
class DocumentRecordAdmin(admin.ModelAdmin):
    list_display = ("document_id", "title", "document_type", "authenticity_assessment", "qa_status")
    list_filter = ("document_type", "authenticity_assessment", "qa_status")
    search_fields = ("document_id", "title")
    readonly_fields = ("document_id",)
