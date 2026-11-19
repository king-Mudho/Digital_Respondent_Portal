"""Sending a participant the study's information documents when they ask for them (PI, 19 Nov 2026).

Research assistants phoning Main-400 respondents and key informants are often asked "send me something about the
study so I can read it first". The PI marks which documents from the Research Clearance register go out for that
("Send to participants who ask about the study", ClearanceDocument.in_study_brief); a research assistant then sends
them to the person they are talking to, from that person's case or KII record, or from Calls:

* WhatsApp from the study number -- the documents as one PDF, with a short message. Only inside the 24 hours after the
  person's own last WhatsApp message, as for every free-text WhatsApp message (Meta's rule);
* email from the study address, each document attached;
* WhatsApp from the research assistant's own phone -- a click-to-chat message carrying a link to the same PDF, for
  when the study number cannot write to them. The research assistant records that they sent it.

Every document sent is checked for the phrases a participant must never see (AGENTS.md rule 2,
COMMUNICATION_BLOCKED_PHRASES): when it is marked for sending, and again every time it is sent, so a file replaced
later cannot slip through. A document that fails is never sent -- unless the PI has recorded, for that exact file, that
it goes as it is (a wording exception, with a reason; 19 Nov 2026). A replaced file loses the exception. Nothing here asks for or records consent: this is
information before taking part, like the introduction itself, and a participant who withdrew is never sent anything.
"""

import os
from io import BytesIO

from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action

from .models import ClearanceDocument
from .services import open_file

BRIEF_NAME = "ABF-FST-Study-Information.pdf"
TEMPLATE_NAME = "study_brief_message"
EMAIL_SUBJECT = "Information about the ABF-FST research study"
CHANNELS = ("WHATSAPP", "EMAIL")
_text_cache: dict = {}
_pack_cache: dict = {}


class BriefError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


# --- The documents ---------------------------------------------------------------------------------------------------

def _has_file(doc: ClearanceDocument) -> bool:
    return bool(doc.file_ref) and os.path.exists(os.path.join(settings.PRIVATE_DATA_ROOT, doc.file_ref))


def document_text(doc: ClearanceDocument) -> str:
    """The text of a PDF document, for the phrase check ("" for an image or a PDF with no text layer)."""
    if not _has_file(doc):
        return ""
    key = (doc.pk, doc.file_ref)
    if key not in _text_cache:
        text = ""
        path, filename, content_type = open_file(doc)
        if filename.lower().endswith(".pdf") or (content_type or "").endswith("pdf"):
            from pypdf import PdfReader

            try:
                text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
            except Exception:  # a damaged PDF must not take the Research Clearance screen down with it
                text = ""
        _text_cache[key] = text
    return _text_cache[key]


def blocked_phrase_in(doc: ClearanceDocument) -> str:
    """The first phrase a participant must never see that this document contains, or ""."""
    from apps.messaging.communications import _blocked_phrase

    return _blocked_phrase(" ".join(f"{doc.title} {doc.description} {document_text(doc)}".split()))


def unexcused_phrase(doc: ClearanceDocument) -> str:
    """The forbidden phrase that stops this document being sent: blocked_phrase_in(), unless the PI recorded that this
    exact file goes as it is (ClearanceDocument.has_wording_exception). "" when it may be sent."""
    return "" if doc.has_wording_exception else blocked_phrase_in(doc)


def brief_documents() -> list[ClearanceDocument]:
    """The documents marked for sending: active, with a file on disk, in the register's order."""
    return [d for d in ClearanceDocument.objects.filter(in_study_brief=True, active=True).order_by("display_order", "pk")
            if _has_file(d)]


def _checked_documents() -> list[ClearanceDocument]:
    docs = brief_documents()
    if not docs:
        raise BriefError("no_documents", "No study documents are set up for sending yet. The PI chooses them on "
                                         "Research Clearance (\"Send to participants who ask about the study\").", 409)
    for doc in docs:
        phrase = unexcused_phrase(doc)
        if phrase:
            raise BriefError("blocked_phrase", f"\"{doc.title}\" contains \"{phrase}\", which participants must never be "
                                               "shown. Nothing was sent. The PI needs to replace that document.", 409)
    return docs


def brief_pack() -> bytes | None:
    """The PDF documents marked for sending, combined into one PDF; None when there are none."""
    from pypdf import PdfReader, PdfWriter

    docs = [d for d in brief_documents() if d.file_name.lower().endswith(".pdf") or (d.file_content_type or "").endswith("pdf")]
    if not docs or any(unexcused_phrase(d) for d in docs):
        return None
    key = tuple((d.pk, d.file_ref) for d in docs)
    if key not in _pack_cache:
        writer = PdfWriter()
        for doc in docs:
            path, _, _ = open_file(doc)
            for page in PdfReader(path).pages:
                writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        _pack_cache.clear()
        _pack_cache[key] = out.getvalue()
    return _pack_cache[key]


def brief_url() -> str:
    """Where the combined PDF can be opened (by WhatsApp, or by the participant from a link), or "" until
    STUDY_LETTERS_KEY is set. The same unguessable key as the study letters (clearance.views.StudyLettersPackView)."""
    key = (getattr(settings, "STUDY_LETTERS_KEY", "") or "").strip()
    return f"https://{settings.APP_DOMAIN}/api/v1/study-letters/{key}/{BRIEF_NAME}" if key else ""


# --- Who it goes to --------------------------------------------------------------------------------------------------

def resolve(user, kind: str, ident: str):
    """The case ("main", sample_id) or KII record ("kii", kii_id) this user may contact; 404 for anything else."""
    from apps.messaging.communications import visible_cases, visible_records

    if kind == "main":
        subject = visible_cases(user).filter(sample_id=ident).first()
    elif kind == "kii":
        subject = visible_records(user).filter(kii_id=ident).first()
    else:
        raise BriefError("invalid_kind", "Say whether this is a Main-400 case or a KII record.")
    if subject is None:
        raise BriefError("not_found", "That case or KII record was not found, or is not assigned to you.", 404)
    return subject


def _withdrawn(subject) -> bool:
    from apps.consent.models import ConsentDecision, ConsentType
    from apps.consent.services import latest_consent

    current = latest_consent(subject, ConsentType.PARTICIPATION)
    return current is not None and current.decision == ConsentDecision.WITHDRAWN


def _recipients(subject) -> dict:
    if hasattr(subject, "kii_id"):
        from apps.kii.messages import kii_recipients

        return kii_recipients(subject)
    from apps.invitations.messages import recipients

    return recipients(subject)


def _org(subject) -> str:
    if hasattr(subject, "kii_id"):
        from apps.contacts.kii_finder import organisation_name

        return organisation_name(subject)
    return subject.organisation.name


def message_text(subject, *, with_link: bool) -> str:
    """The message that goes with the documents: the PI's wording (MessageTemplate study_brief_message), addressed to the
    person by name where one is on file. The line holding {link} is kept only when the documents go as a link (sent
    from the research assistant's phone); from the study number or address they go as the files themselves."""
    from apps.invitations.messages import _greeting_name
    from apps.messaging.models import MessageTemplate

    template = MessageTemplate.objects.filter(name=TEMPLATE_NAME).first()
    body = template.body if template else ""
    who = _recipients(subject)
    name = _greeting_name((who.get("whatsapp_to_name") or who.get("email_to_name") or "").strip())
    lines = [line for line in body.splitlines() if with_link or "{link}" not in line]
    text = "\n".join(lines).replace("{name}", f" {name}" if name else "").replace("{org}", _org(subject))
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.replace("{link}", brief_url()).strip()


def _ident(subject) -> dict:
    return {"kii_id": subject.kii_id} if hasattr(subject, "kii_id") else {"sample_id": subject.sample_id}


def _links(subject) -> dict:
    return {"kii_record": subject} if hasattr(subject, "kii_id") else {"sample_case": subject}


def summary(user, kind: str, ident: str) -> dict:
    """What can be sent to this person, and how: for the panel beside a case, a KII record or a Calls row."""
    from urllib.parse import quote

    from apps.messaging import outbound
    from apps.messaging import twilio_client as tw
    from apps.messaging.hashing import number_hash
    from apps.messaging.outreach import reply_window_open

    subject = resolve(user, kind, ident)
    who = _recipients(subject)
    docs = brief_documents()
    blocked = {d.pk: unexcused_phrase(d) for d in docs}
    problem = ""
    if not docs:
        problem = "No study documents are set up for sending yet. The PI chooses them on Research Clearance."
    elif any(blocked.values()):
        bad = next(d for d in docs if blocked[d.pk])
        problem = f"\"{bad.title}\" contains \"{blocked[bad.pk]}\", which participants must never be shown. The PI needs to replace it."
    elif _withdrawn(subject):
        problem = "This participant withdrew from the study, so nothing is sent to them."
    whatsapp = who.get("whatsapp_to") or ""
    by_hand_text = message_text(subject, with_link=True) if docs and brief_url() else ""
    return {
        "documents": [{"id": d.id, "title": d.title, "file_name": d.file_name, "blocked_phrase": blocked[d.pk]} for d in docs],
        "problem": problem,
        "whatsapp_to": whatsapp, "whatsapp_to_name": who.get("whatsapp_to_name") or "",
        "whatsapp_window_open": bool(whatsapp) and reply_window_open(number_hash(whatsapp)),
        "whatsapp_configured": tw.credentials_set() and bool((settings.TWILIO_WHATSAPP_FROM or "").strip()) and bool(brief_url()),
        "email_to": who.get("email_to") or "", "email_configured": outbound.email_configured(),
        "by_hand_link": f"https://wa.me/{whatsapp}?text={quote(by_hand_text)}" if whatsapp and by_hand_text and not problem else "",
        "message": by_hand_text,
    }


def send(user, kind: str, ident: str, channel: str) -> dict:
    """Send the documents to the person on this case or KII record from the study number or address."""
    from apps.messaging import outbound
    from apps.messaging.hashing import number_hash
    from apps.messaging.models import MessageChannel, MessagePurpose
    from apps.messaging.outreach import reply_window_open

    if channel not in CHANNELS:
        raise BriefError("invalid_channel", "Choose WhatsApp or email.")
    subject = resolve(user, kind, ident)
    if _withdrawn(subject):
        raise BriefError("withdrawn", "This participant withdrew from the study, so nothing is sent to them.", 409)
    docs = _checked_documents()
    who = _recipients(subject)
    try:
        if channel == "WHATSAPP":
            number = who.get("whatsapp_to") or ""
            if not number:
                raise BriefError("no_mobile", "No WhatsApp number is on file for this person.")
            if not reply_window_open(number_hash(number)):
                raise BriefError("window_closed", "WhatsApp only lets the study number write to someone within 24 hours of "
                                                  "their own last message. Use \"Send from my phone\" instead.", 409)
            url = brief_url()
            if not url or brief_pack() is None:
                raise BriefError("no_pdf", "The documents can't be sent on WhatsApp from the study number (they need to be "
                                           "PDFs, and STUDY_LETTERS_KEY set). Send them by email or from your phone.", 409)
            message = outbound.send(channel=MessageChannel.WHATSAPP, number=number, purpose=MessagePurpose.STUDY_INFO,
                                    wa_media_url=url, wa_text=message_text(subject, with_link=False), user=user,
                                    record_text=f"[Document: {BRIEF_NAME}] " + message_text(subject, with_link=False),
                                    **_links(subject))
        else:
            attachments = []
            for doc in docs:
                path, filename, content_type = open_file(doc)
                with open(path, "rb") as fh:
                    attachments.append((filename, fh.read(), content_type or "application/pdf"))
            message = outbound.send_email(to=who.get("email_to") or "", subject=EMAIL_SUBJECT,
                                          body=message_text(subject, with_link=False), purpose=MessagePurpose.STUDY_INFO,
                                          user=user, attachments=attachments, **_links(subject))
    except outbound.OutboundError as exc:
        raise BriefError(exc.code, str(exc), exc.status) from exc
    log_action("study_brief.sent", subject, {
        **_ident(subject), "channel": channel, "recipient": message.to_masked, "documents": [d.pk for d in docs],
        "provider_message": message.pk, "user_id": user.id,
    }, user=user)
    return {"sent_to": message.to_masked, "channel": channel, "status": message.status}


def record_by_hand(user, kind: str, ident: str) -> dict:
    """The research assistant sent the documents' link from their own phone ("Send from my phone"): recorded on the
    timeline, so the next person to call knows they have it."""
    from apps.contacts.models import ContactChannel, ContactEvent, ContactOutcome

    subject = resolve(user, kind, ident)
    if _withdrawn(subject):
        raise BriefError("withdrawn", "This participant withdrew from the study, so nothing is sent to them.", 409)
    docs = _checked_documents()
    event = ContactEvent.objects.create(channel=ContactChannel.WHATSAPP, occurred_at=timezone.now(),
                                        outcome=ContactOutcome.STUDY_INFO_SENT, ra=user,
                                        notes="Sent the study information documents from my own WhatsApp", **_links(subject))
    log_action("study_brief.sent_by_hand", subject, {
        **_ident(subject), "channel": "WHATSAPP_BY_HAND", "documents": [d.pk for d in docs], "contact_event": event.pk,
        "user_id": user.id,
    }, user=user)
    return {"recorded": True}
