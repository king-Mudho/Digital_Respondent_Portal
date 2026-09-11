from django.contrib import admin

from .models import Appointment, ContactEvent, Respondent


@admin.register(Respondent)
class RespondentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "sample_case", "role_category", "is_eligible")
    list_filter = ("role_category", "is_eligible")
    search_fields = ("full_name", "sample_case__sample_id")


@admin.register(ContactEvent)
class ContactEventAdmin(admin.ModelAdmin):
    list_display = ("sample_case", "channel", "outcome", "occurred_at", "ra")
    list_filter = ("channel", "outcome")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("scheduled_for", "mode", "status", "sample_case", "kii_record")
    list_filter = ("mode", "status")
