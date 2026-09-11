"""
WhatsApp Business Platform client (Meta Cloud API shape).

Cannot be live-tested without a real Meta Business account and Meta-
approved utility-category templates -- both are Phase 0 dependencies not
yet provisioned (docs/27_AGENT_EXECUTION_PLAN.md "Open questions",
docs/12_CONTACT_CRM_AND_MESSAGING.md's 3-5 business day review). This client
is built against the documented Cloud API request shape so it's ready to
point at a real account once one exists; `send_template_message` raises
`WhatsAppNotConfigured` rather than silently no-opping if credentials are
missing, so a misconfigured deployment fails loudly instead of pretending
to send.
"""

import requests
from django.conf import settings


class WhatsAppNotConfigured(Exception):
    pass


class WhatsAppClient:
    def __init__(self, base_url: str | None = None, api_token: str | None = None):
        self.base_url = base_url or settings.WHATSAPP_API_BASE_URL
        self.api_token = api_token or settings.WHATSAPP_API_TOKEN

    def send_template_message(self, *, to_phone: str, template_name: str, params: list[str] | None = None) -> dict:
        if not self.base_url or not self.api_token:
            raise WhatsAppNotConfigured(
                "WHATSAPP_API_BASE_URL/WHATSAPP_API_TOKEN are not set -- no WhatsApp "
                "Business Platform account has been provisioned yet."
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": (
                    [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
                    if params
                    else []
                ),
            },
        }
        response = requests.post(
            f"{self.base_url}/messages",
            headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
