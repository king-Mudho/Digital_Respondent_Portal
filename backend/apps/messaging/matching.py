"""Which Main-400 case or KII record a number or an email address belongs to (2026-10-12).

Used for messages that arrive -- a WhatsApp message from a number with no "ask first" introduction, an email to the
study address -- and for answering them. Only the people recorded on a case (Respondent) or a KII record count:
a match is what lets a message be kept at all (apps/messaging/mailbox.py stores nothing it cannot match).

When the same number or address is on more than one record, the one contacted most recently wins, so a reply lands
in the conversation it answers.
"""

from django.db.models import Max

from apps.contacts.contact_text import CHUNK_SPLIT, clean, mobile_number

from .hashing import email_hash, number_hash


def numbers_in(field: str) -> list[str]:
    """Every mobile in a contact field, as international digits (263771234567)."""
    out = []
    for chunk in CHUNK_SPLIT.split(clean(field)):
        number = mobile_number(chunk).lstrip("+")
        if not number:
            digits = "".join(ch for ch in chunk if ch.isdigit())
            number = digits if chunk.strip().startswith("+") and 10 <= len(digits) <= 15 else ""
        if number and number not in out:
            out.append(number)
    return out


def _latest_contact(model_field: str, ids: list[int]) -> dict[int, object]:
    from .models import ProviderMessage

    rows = (ProviderMessage.objects.filter(**{f"{model_field}__in": ids}).values(model_field)
            .annotate(last=Max("created_at")))
    return {row[model_field]: row["last"] for row in rows}


def _pick(cases: list, records: list):
    """(case, record) -- one of them -- preferring whichever was contacted most recently."""
    if not cases and not records:
        return None, None
    case_last = _latest_contact("sample_case", [c.id for c in cases]) if cases else {}
    record_last = _latest_contact("kii_record", [r.id for r in records]) if records else {}
    candidates = [(case_last.get(c.id), 1, c.id, c, None) for c in cases]
    candidates += [(record_last.get(r.id), 0, r.id, None, r) for r in records]
    candidates.sort(key=lambda c: (c[0] is not None, c[0] or 0, c[1], c[2]), reverse=True)
    _, _, _, case, record = candidates[0]
    return case, record


def find_by_number(digits: str):
    """(SampleCase or None, KIIRecord or None) holding this mobile number."""
    from apps.contacts.models import Respondent
    from apps.kii.models import KIIRecord

    digits = "".join(ch for ch in digits or "" if ch.isdigit())
    if not digits:
        return None, None
    tail = digits[-9:]  # cheap pre-filter on the last nine digits, then an exact comparison
    cases = {}
    for person in Respondent.objects.exclude(phone="", whatsapp_number="").select_related("sample_case"):
        raw = "".join(ch for ch in person.phone + person.whatsapp_number if ch.isdigit())
        if tail in raw and digits in numbers_in(person.phone) + numbers_in(person.whatsapp_number):
            cases[person.sample_case_id] = person.sample_case
    records = [r for r in KIIRecord.objects.exclude(phone="", whatsapp_number="")
               if digits in numbers_in(r.phone) + numbers_in(r.whatsapp_number)]
    return _pick(list(cases.values()), records)


def find_by_email(address: str):
    """(SampleCase or None, KIIRecord or None) holding this email address."""
    from apps.contacts.models import Respondent
    from apps.kii.models import KIIRecord

    address = (address or "").strip()
    if "@" not in address:
        return None, None
    cases = {p.sample_case_id: p.sample_case for p in Respondent.objects.filter(email__iexact=address).select_related("sample_case")}
    records = list(KIIRecord.objects.filter(email__iexact=address))
    return _pick(list(cases.values()), records)


def known_email_addresses() -> set[str]:
    """Every address on a case or KII record, lower-cased: the only senders whose email is ever read in full."""
    from apps.contacts.models import Respondent
    from apps.kii.models import KIIRecord

    found = {e.strip().lower() for e in Respondent.objects.exclude(email="").values_list("email", flat=True)}
    found |= {e.strip().lower() for e in KIIRecord.objects.exclude(email="").values_list("email", flat=True)}
    return {e for e in found if "@" in e}


def contact_numbers(case=None, record=None) -> list[str]:
    """Every mobile recorded for a case's people or a KII record."""
    out = []
    if case is not None:
        for person in case.respondents.all():
            out += numbers_in(person.whatsapp_number) + numbers_in(person.phone)
    if record is not None:
        out += numbers_in(record.whatsapp_number) + numbers_in(record.phone)
    return list(dict.fromkeys(out))


def number_matching(hashed: str, case=None, record=None) -> str:
    """The recorded number whose hash is `hashed` -- to answer someone without having kept their number."""
    for number in contact_numbers(case, record):
        if number_hash(number) == hashed:
            return number
    return ""


def address_matching(hashed: str, case=None, record=None) -> str:
    candidates = [p.email for p in case.respondents.all()] if case is not None else []
    if record is not None:
        candidates.append(record.email)
    for address in candidates:
        if address and email_hash(address) == hashed:
            return address
    return ""
