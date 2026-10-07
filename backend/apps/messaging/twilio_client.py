"""SMS and WhatsApp through Twilio's Messages API (added 2026-10-07, PI decision).

The portal's only way to send a text message itself: invitations (one case at a time and in batches) and the
automatic Day 2 / Day 7 reminders. Each channel is offered only once its own settings are in place
(deploy/configure-twilio.sh), so SMS can go live while the WhatsApp sender and its templates wait for Meta.

What Zimbabwe allows (Twilio's country guidelines, checked 2026-10-07): an SMS sender must be a registered name or an
international number; two-way SMS is not supported, so nobody can reply STOP (TWILIO_SMS_OPT_OUT_LINE carries the
PI-approved alternative); about US$0.32 per segment. A WhatsApp business-initiated message must be a Meta-approved
template (ContentSid), never free text.

Uses `requests`, like apps/proit/muse.py, rather than adding the Twilio SDK for two POSTs and one signature check.
"""

import base64
import hashlib
import hmac
import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API = "https://api.twilio.com/2010-04-01"

# Twilio is busy or had a fault of its own: wait and ask again, as apps/proit/muse.py does for Meta.
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}

# Twilio's own error codes, in words a coordinator can act on. Anything else keeps Twilio's message.
FRIENDLY = {
    20003: "Twilio did not accept the account details. Re-run deploy/configure-twilio.sh with the Account SID and Auth Token.",
    20005: "The Twilio account is suspended or out of credit. Add credit in the Twilio console.",
    21211: "That number is not a valid mobile number.",
    21408: "Sending to this country is not switched on in the Twilio account (Messaging > Geo permissions).",
    21610: "This number has asked not to receive messages from the study.",
    21612: "Twilio cannot send to this number from the study's sender.",
    21614: "That number is not a mobile number, so it cannot receive SMS.",
    21606: "The study's sender is not set up to send this kind of message. Check TWILIO_SMS_FROM / TWILIO_WHATSAPP_FROM.",
    21656: "The WhatsApp template's variables do not match what Meta approved.",
    63007: "The study's WhatsApp sender is not registered on Twilio yet.",
    63016: "WhatsApp only allows an approved template here. Check the template id in configure-twilio.sh.",
}


class TwilioError(Exception):
    def __init__(self, message: str, *, code=None, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(message)


def _account() -> tuple[str, str]:
    return (settings.TWILIO_ACCOUNT_SID or "").strip(), (settings.TWILIO_AUTH_TOKEN or "").strip()


def credentials_set() -> bool:
    sid, token = _account()
    return bool(sid and token)


def sms_configured() -> bool:
    return credentials_set() and bool((settings.TWILIO_SMS_FROM or "").strip())


def whatsapp_configured(kii: bool = False) -> bool:
    template = settings.TWILIO_WA_CONTENT_KII_INVITATION if kii else settings.TWILIO_WA_CONTENT_INVITATION
    return credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip()) and bool((template or "").strip())


REMINDER_TEMPLATES = {
    "drp_reminder_day2": "TWILIO_WA_CONTENT_REMINDER_DAY2",
    "drp_reminder_day7_final": "TWILIO_WA_CONTENT_REMINDER_DAY7",
}


def whatsapp_reminder_template(template_name: str) -> str:
    """The approved Twilio template for this reminder, or "" when WhatsApp reminders are not set up for it."""
    setting = REMINDER_TEMPLATES.get(template_name)
    content = (getattr(settings, setting, "") or "").strip() if setting else ""
    ready = credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip())
    return content if ready else ""


def status_callback_url() -> str:
    """Where Twilio reports delivery. Built from APP_DOMAIN (AGENTS.md rule 9); the same string is what the signature
    is checked against, so it must never be rebuilt from the incoming request (behind nginx that reads http://)."""
    return f"https://{settings.APP_DOMAIN}/api/v1/twilio/status/"


def mask(number: str) -> str:
    digits = "".join(ch for ch in number or "" if ch.isdigit())
    return f"+{digits[:3]} ••• {digits[-3:]}" if len(digits) > 6 else "•••"


def with_opt_out(text: str) -> str:
    line = (settings.TWILIO_SMS_OPT_OUT_LINE or "").strip()
    return f"{text} {line}" if line else text


def sms_segments(text: str) -> int:
    """How many SMS segments Twilio will charge for: 160 characters (153 per part when split) in the basic GSM
    alphabet, 70 (67) once any other character -- a curly quote, an accent -- is in the message."""
    gsm = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
              "¿abcdefghijklmnopqrstuvwxyzäöñüà^{}\\[~]|€")
    if all(ch in gsm for ch in text):
        length = len(text) + sum(1 for ch in text if ch in "^{}\\[~]|€")
        single, part = 160, 153
    else:
        length, single, part = len(text), 70, 67
    return 1 if length <= single else -(-length // part)


def _friendly(response) -> TwilioError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = body.get("code")
    message = FRIENDLY.get(code) or body.get("message") or f"Twilio answered {response.status_code}."
    return TwilioError(message, code=code, status=response.status_code)


def _post(data: dict, *, post=None, delays=None, sleep=time.sleep) -> dict:
    # Looked up at call time, not bound as a default argument when the module loads.
    post = post or requests.post
    sid, token = _account()
    if not (sid and token):
        raise TwilioError("Twilio is not set up on the server yet (deploy/configure-twilio.sh).")
    delays = list(settings.AI_TRANSIENT_RETRY_DELAYS if delays is None else delays)
    url = f"{API}/Accounts/{sid}/Messages.json"
    for attempt in range(len(delays) + 1):
        retries_left = attempt < len(delays)
        try:
            response = post(url, data=data, auth=(sid, token), timeout=30)
        except requests.ConnectionError:
            if not retries_left:
                raise TwilioError("Twilio could not be reached. Try again in a few minutes.")
            logger.warning("Twilio could not be reached; retrying in %ss", delays[attempt])
            sleep(delays[attempt])
            continue
        if response.status_code in TRANSIENT_STATUSES and retries_left:
            logger.warning("Twilio returned %s; retrying in %ss", response.status_code, delays[attempt])
            sleep(delays[attempt])
            continue
        if response.status_code >= 400:
            raise _friendly(response)
        return response.json()
    raise AssertionError("unreachable")  # every path above returns or raises


def send_sms(to_digits: str, body: str, **kwargs) -> dict:
    """One SMS to an international number given as digits (263771234567). Returns Twilio's message (sid, status)."""
    return _post({
        "To": f"+{to_digits}", "From": settings.TWILIO_SMS_FROM.strip(), "Body": with_opt_out(body),
        "StatusCallback": status_callback_url(),
    }, **kwargs)


def send_whatsapp(to_digits: str, content_sid: str, variables: dict | None = None, **kwargs) -> dict:
    """One WhatsApp template message. Business-initiated WhatsApp must be a Meta-approved template, never free text."""
    data = {
        "To": f"whatsapp:+{to_digits}", "From": f"whatsapp:{settings.TWILIO_WHATSAPP_FROM.strip()}",
        "ContentSid": content_sid, "StatusCallback": status_callback_url(),
    }
    if variables:
        data["ContentVariables"] = json.dumps({str(k): str(v) for k, v in variables.items()})
    return _post(data, **kwargs)


def valid_signature(url: str, params: dict, signature: str) -> bool:
    """Twilio's X-Twilio-Signature: base64 HMAC-SHA1, keyed with the Auth Token, of the URL followed by every POST
    parameter name and value sorted by name. Anything that does not match was not sent by Twilio."""
    _, token = _account()
    if not (token and signature):
        return False
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)
