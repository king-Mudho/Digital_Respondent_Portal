from django.contrib import admin

from .models import QAEvent, QARuleThreshold


@admin.register(QARuleThreshold)
class QARuleThresholdAdmin(admin.ModelAdmin):
    list_display = ("code", "value", "effective_from", "set_by")


@admin.register(QAEvent)
class QAEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "decision", "rule_triggered", "reviewer", "submission", "kii_record", "document_record")
    list_filter = ("decision",)
    readonly_fields = ("created_at",)
