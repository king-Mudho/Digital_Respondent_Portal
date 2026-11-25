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
import re
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
    """The approved Twilio template for this reminder, or "" when WhatsApp reminders are not set up for it -- including
    while Meta has the template pending or rejected (2026-10-13: on 13 Oct the 08:00 run sent 148 WhatsApp reminders on
    pending templates and 120 came back undelivered with error 63016). The reminder then goes by SMS, or waits on
    Follow-ups."""
    setting = REMINDER_TEMPLATES.get(template_name)
    content = (getattr(settings, setting, "") or "").strip() if setting else ""
    ready = credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip())
    return content if ready and content and not content_waiting(content) else ""


def inbound_url() -> str:
    """Where Twilio posts messages people send to the study's WhatsApp number (set on the WhatsApp sender in the Twilio
    console). Like status_callback_url(), the signature is checked against exactly this string."""
    return f"https://{settings.APP_DOMAIN}/api/v1/twilio/inbound/"


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


def fetch_message(message_sid: str, *, get=None) -> dict:
    """Twilio's current record of one message (status, error_code, error_message), for outbound.recheck_statuses()."""
    get = get or requests.get
    sid, token = _account()
    if not (sid and token):
        raise TwilioError("Twilio is not set up on the server yet (deploy/configure-twilio.sh).")
    try:
        response = get(f"{API}/Accounts/{sid}/Messages/{message_sid}.json", auth=(sid, token), timeout=30)
    except requests.ConnectionError:
        raise TwilioError("Twilio could not be reached. Try again in a few minutes.")
    if response.status_code >= 400:
        raise _friendly(response)
    return response.json()


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


def send_whatsapp_text(to_digits: str, body: str, **kwargs) -> dict:
    """A free-text WhatsApp reply. WhatsApp allows one only within 24 hours of the person's own last message to the
    study (outreach.reply_window_open() checks that first); outside it Twilio refuses with 63016."""
    return _post({
        "To": f"whatsapp:+{to_digits}", "From": f"whatsapp:{settings.TWILIO_WHATSAPP_FROM.strip()}", "Body": body,
        "StatusCallback": status_callback_url(),
    }, **kwargs)


def send_whatsapp_media(to_digits: str, media_url: str, body: str = "", **kwargs) -> dict:
    """A document, picture, video or voice note, inside the same 24 hours as a free-text reply. Twilio fetches
    `media_url` itself; `body` is the caption (WhatsApp shows none on a voice note, so none is sent with one)."""
    data = {
        "To": f"whatsapp:+{to_digits}", "From": f"whatsapp:{settings.TWILIO_WHATSAPP_FROM.strip()}", "MediaUrl": media_url,
        "StatusCallback": status_callback_url(),
    }
    if body:
        data["Body"] = body
    return _post(data, **kwargs)


def media_base_url() -> str:
    """Where Twilio fetches an outgoing WhatsApp file from (apps/messaging/media_out.py). Built from APP_DOMAIN."""
    return f"https://{settings.APP_DOMAIN}/api/v1/twilio/media/"


def study_whatsapp_link(text: str = "YES") -> str:
    """The tap-to-reply link an SMS carries: opens a chat with the study's WhatsApp number with `text` typed in."""
    from urllib.parse import quote

    digits = "".join(ch for ch in settings.TWILIO_WHATSAPP_FROM or "" if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(text)}" if digits else ""


def valid_signature(url: str, params: dict, signature: str) -> bool:
    """Twilio's X-Twilio-Signature: base64 HMAC-SHA1, keyed with the Auth Token, of the URL followed by every POST
    parameter name and value sorted by name. Anything that does not match was not sent by Twilio."""
    _, token = _account()
    if not (token and signature):
        return False
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)


# The WhatsApp templates, in the order configure-twilio.sh asks for them, with the name each has in Twilio.
TEMPLATE_SETTINGS = [
    ("TWILIO_WA_CONTENT_INVITATION", "Main-400 invitation"),
    ("TWILIO_WA_CONTENT_KII_INVITATION", "KII invitation"),
    ("TWILIO_WA_CONTENT_REMINDER_DAY2", "Day 2 reminder"),
    ("TWILIO_WA_CONTENT_REMINDER_DAY7", "Day 7 reminder"),
    ("TWILIO_WA_CONTENT_INTRO", "Introduction (ask first)"),
    ("TWILIO_WA_CONTENT_INTRO_REMINDER", "Introduction reminder"),
    ("TWILIO_WA_CONTENT_KII_INTRO", "KII introduction (ask first)"),
    ("TWILIO_WA_CONTENT_KII_INTRO_REMINDER", "KII introduction reminder"),
    ("TWILIO_WA_CONTENT_INTRO_NEXT", "Introduction, new wording (used once approved)"),
    ("TWILIO_WA_CONTENT_KII_INTRO_NEXT", "KII introduction, new wording (used once approved)"),
    ("TWILIO_WA_CONTENT_THANK_YOU", "Thank you for taking part (used once approved)"),
    ("TWILIO_WA_CONTENT_INTRO_LETTERS", "Introduction with the study letters (used once approved)"),
    ("TWILIO_WA_CONTENT_KII_INTRO_LETTERS", "KII introduction with the study letters (used once approved)"),
    ("TWILIO_WA_CONTENT_STUDY_INFO", "Study information PDF (used once approved)"),
]
APPROVALS_CACHE_SECONDS = 600


def template_approvals(*, get=None) -> list[dict]:
    """Meta's decision on each configured WhatsApp template, read from Twilio's Content API (2026-10-12) and cached for
    ten minutes -- Communications shows it so nobody sends while templates are still pending. Read-only."""
    from django.core.cache import cache

    configured = [(setting, label, (getattr(settings, setting, "") or "").strip()) for setting, label in TEMPLATE_SETTINGS]
    if not credentials_set() or not any(sid for _, _, sid in configured):
        return []
    key = "twilio-template-approvals:" + ",".join(sid for _, _, sid in configured)
    cached = cache.get(key)
    if cached is not None:
        return cached
    get = get or requests.get
    out = []
    for setting, label, sid in configured:
        row = {"label": label, "sid": sid, "name": "", "status": "not set", "category": "", "rejection_reason": ""}
        if sid:
            try:
                response = get(f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests", auth=_account(), timeout=15)
                data = ((response.json() or {}).get("whatsapp") or {}) if response.ok else {}
                row.update(name=data.get("name", ""), status=(data.get("status") or "unknown").lower(),
                           category=(data.get("category") or "").lower(), rejection_reason=data.get("rejection_reason") or "")
            except (requests.RequestException, ValueError):
                row["status"] = "unknown"
        out.append(row)
    cache.set(key, out, APPROVALS_CACHE_SECONDS)
    return out


LIMIT_CACHE_SECONDS = 1800


def _parse_limit(text: str):
    """"250 Customers/24hr" -> 250, "2K Customers/24hr" -> 2000, "Unlimited" -> None (no limit), unreadable -> 0."""
    value = (text or "").strip().upper()
    if not value:
        return 0
    if value.startswith("UNLIMITED"):
        return None
    match = re.match(r"([\d.,]+)\s*([KM]?)", value)
    if not match:
        return 0
    number = float(match.group(1).replace(",", ""))
    return int(number * {"": 1, "K": 1000, "M": 1000000}[match.group(2)])


def meta_messaging_limit(*, get=None):
    """Meta's current limit on how many different people the study's WhatsApp number may start conversations with in
    24 hours, from Twilio's Senders API; cached for half an hour. None means no limit. When Twilio cannot be asked, the
    last value read is used, and 250 (Meta's starting tier) if there is none."""
    from django.core.cache import cache

    number = "".join(ch for ch in (settings.TWILIO_WHATSAPP_FROM or "") if ch.isdigit())
    if not number or not credentials_set():
        return 250
    cached = cache.get("twilio-meta-limit")
    if cached is not None:
        return None if cached == "none" else cached
    get = get or requests.get
    try:
        response = get("https://messaging.twilio.com/v2/Channels/Senders", params={"Channel": "whatsapp", "PageSize": 50},
                       auth=_account(), timeout=15)
        senders = (response.json() or {}).get("senders", []) if response.ok else []
        sender = next((s for s in senders if number in "".join(ch for ch in s.get("sender_id", "") if ch.isdigit())), None)
        limit = _parse_limit(((sender or {}).get("properties") or {}).get("messaging_limit", "")) if sender else 0
    except (requests.RequestException, ValueError):
        limit = 0
    if limit == 0:  # not readable: the last known value, else Meta's starting tier
        last = cache.get("twilio-meta-limit-last")
        return None if last == "none" else (last or 250)
    cache.set("twilio-meta-limit", "none" if limit is None else limit, LIMIT_CACHE_SECONDS)
    cache.set("twilio-meta-limit-last", "none" if limit is None else limit, 7 * 24 * 3600)
    return limit


def template_waiting(setting: str, *, approvals=None) -> str:
    """Meta's status for the template in `setting` when it is known and not yet approved ("pending", "rejected"...),
    else "". A batch refuses WhatsApp while its template waits (2026-10-13): Twilio accepts a message on an unapproved
    template and it fails later (error 63016), so the batch would have reported it sent. "unknown" -- Twilio could
    not be asked -- does not block."""
    return content_waiting((getattr(settings, setting, "") or "").strip(), approvals=approvals)


def content_approved(sid: str, *, approvals=None) -> bool:
    """True only when Meta's answer for this Content SID is known and "approved" (2026-10-18). Stricter than
    content_waiting(), which lets an unknown status through: a replacement template is used only on a definite yes."""
    if not sid:
        return False
    rows = template_approvals() if approvals is None else approvals
    return any(row["sid"] == sid and row["status"] == "approved" for row in rows)


def content_waiting(sid: str, *, approvals=None) -> str:
    """template_waiting() for a Content SID rather than the setting that holds it."""
    if not sid:
        return ""
    for row in template_approvals() if approvals is None else approvals:
        if row["sid"] == sid and row["status"] not in ("approved", "unknown"):
            return row["status"]
    return ""


BALANCE_CACHE_SECONDS = 600


def account_balance(*, get=None, today=None) -> dict:
    """What is left on the study's Twilio account and how fast it is being spent (22 Nov 2026), for the Cost screen:
    the balance, this month's and the last 7 days' spending (all of it, and WhatsApp alone), the daily average over
    those 7 days, and how many days the balance lasts at that rate. Read-only, cached ten minutes. {"error": ...} when
    Twilio cannot be asked; never raises."""
    from datetime import timedelta

    from django.core.cache import cache
    from django.utils import timezone

    if not credentials_set():
        return {"configured": False}
    cached = cache.get("twilio-balance")
    if cached is not None:
        return cached
    get = get or requests.get
    sid = _account()[0]
    base = f"https://api.twilio.com/2010-04-01/Accounts/{sid}"
    today = today or timezone.localdate()
    month_start, week_start = today.replace(day=1), today - timedelta(days=6)

    def spent(category: str, start) -> tuple[float, int]:
        response = get(f"{base}/Usage/Records.json", auth=_account(), timeout=15,
                       params={"Category": category, "StartDate": start.isoformat(), "EndDate": today.isoformat()})
        rows = (response.json() or {}).get("usage_records", []) if response.ok else []
        return (round(sum(float(r.get("price") or 0) for r in rows), 2), int(sum(float(r.get("count") or 0) for r in rows)))

    try:
        response = get(f"{base}/Balance.json", auth=_account(), timeout=15)
        if not response.ok:
            return {"configured": True, "error": f"Twilio answered {response.status_code}."}
        body = response.json() or {}
        balance = round(float(body.get("balance") or 0), 2)
        month_total, _ = spent("totalprice", month_start)
        week_total, _ = spent("totalprice", week_start)
        month_wa, month_wa_count = spent("channels-whatsapp", month_start)
        week_wa, week_wa_count = spent("channels-whatsapp", week_start)
    except (requests.RequestException, ValueError, TypeError) as exc:
        return {"configured": True, "error": f"Twilio could not be reached ({type(exc).__name__})."}
    per_day = round(week_total / 7, 2)
    days_left = int(balance // per_day) if per_day > 0 else None
    low = balance < settings.TWILIO_BALANCE_WARN_USD or (days_left is not None and days_left < settings.TWILIO_BALANCE_WARN_DAYS)
    result = {
        "configured": True, "error": "", "balance": balance, "currency": (body.get("currency") or "USD").upper(),
        "spent_this_month": month_total, "spent_last_7_days": week_total,
        "whatsapp_this_month": month_wa, "whatsapp_messages_this_month": month_wa_count,
        "whatsapp_last_7_days": week_wa, "whatsapp_messages_last_7_days": week_wa_count,
        "per_day": per_day, "days_left": days_left,
        "runs_out_on": (today + timedelta(days=days_left)).isoformat() if days_left is not None else None,
        "low": low, "warn_usd": settings.TWILIO_BALANCE_WARN_USD, "warn_days": settings.TWILIO_BALANCE_WARN_DAYS,
        "read_at": timezone.now().isoformat(),
    }
    cache.set("twilio-balance", result, BALANCE_CACHE_SECONDS)
    return result
