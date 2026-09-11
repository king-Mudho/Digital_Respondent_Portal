from django.contrib import admin

from .models import MessageLog, MessageTemplate, ReminderSequenceStep


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "category", "meta_approval_status")


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sample_case", "kii_record", "template", "channel", "status", "triggered_by")
    list_filter = ("channel", "status")


@admin.register(ReminderSequenceStep)
class ReminderSequenceStepAdmin(admin.ModelAdmin):
    list_display = ("day_offset", "channel", "template", "label")
