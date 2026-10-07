from rest_framework import serializers

from .models import InvitationToken


class InvitationTokenSerializer(serializers.ModelSerializer):
    """Status/lifecycle fields only. token_hash and manual_code_hash are
    never serialized -- the only place a raw token or manual code is ever
    visible is the immediate response to POST /api/v1/invitations/ that
    created it (docs/10_INVITATION_AND_CONSENT.md: "never store or log
    them"); after that, this is the closest an admin gets to it again."""

    # What the portal itself sent for this invitation through Twilio, and what Twilio says happened (2026-10-07).
    deliveries = serializers.SerializerMethodField()

    class Meta:
        model = InvitationToken
        fields = ["id", "status", "channel", "invitation_wave", "issued_at", "expires_at", "revoked_at", "revoked_reason",
                  "deliveries"]
        read_only_fields = fields

    def get_deliveries(self, token):
        return deliveries(token.provider_messages.all())


def deliveries(messages) -> list[dict]:
    return [{"channel": m.channel, "status": m.status, "to": m.to_masked, "sent_at": m.created_at,
             "error": m.error_message or m.error_code} for m in messages]
