from django.contrib import admin

from .models import EvidenceSource, PreProfile, PreProfileField


class PreProfileFieldInline(admin.TabularInline):
    model = PreProfileField
    extra = 0
    readonly_fields = ("confidence", "gap_classification")


@admin.register(PreProfile)
class PreProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "sample_case", "kii_record", "researcher_reviewed", "prepopulation_locked_at")
    list_filter = ("researcher_reviewed", "reconciliation_status")
    inlines = [PreProfileFieldInline]
    readonly_fields = ("prepopulation_locked_at",)


@admin.register(PreProfileField)
class PreProfileFieldAdmin(admin.ModelAdmin):
    list_display = ("field_id", "pre_profile", "confidence", "gap_classification", "verification_status")
    list_filter = ("module", "confidence", "gap_classification", "verification_status")
    search_fields = ("field_id",)


@admin.register(EvidenceSource)
class EvidenceSourceAdmin(admin.ModelAdmin):
    list_display = ("source_record_id", "field", "source_title", "source_authority", "source_confidence")
    list_filter = ("source_authority", "source_confidence", "source_conflict")
    search_fields = ("source_record_id", "source_title")
    readonly_fields = ("source_record_id",)
