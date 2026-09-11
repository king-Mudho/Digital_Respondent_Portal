from django.contrib import admin

from .models import InvitationToken


@admin.register(InvitationToken)
class InvitationTokenAdmin(admin.ModelAdmin):
    list_display = ("sample_case", "status", "channel", "invitation_wave", "issued_at", "expires_at")
    list_filter = ("status", "channel")
    search_fields = ("sample_case__sample_id",)
    readonly_fields = ("token_hash", "manual_code_hash")
