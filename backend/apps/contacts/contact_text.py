"""
Splitting free-text contact details into name, phone list and one WhatsApp
number (added 2026-09-15).

The register's "Existing Contact" column mixes everything in one cell:
"Mr J. Mushandu +263772922485/715012852; shamvaagric@gmail.com",
"+263 9 888616, 71363 / 5; +263 773 142 761, 772 830 867",
"Institutional contact to verify", often with an invisible zero-width space
in front. The importer copied that cell into Respondent.full_name, and the
WhatsApp buttons joined every digit of a multi-number field into one number,
so the chat link opened nobody.
"""

import re
from dataclasses import dataclass

INVISIBLE = re.compile(r"[​‌‍⁠﻿]")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PERSON = re.compile(r"^\s*((?:Mr|Mrs|Ms|Miss|Dr|Prof|Eng)\.?\s+[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)")
CHUNK_SPLIT = re.compile(r"[;,/\n]")

UNNAMED = "Organisation contact (name not recorded)"
NOT_IDENTIFIED = "Contact to be identified"


def clean(text: str) -> str:
    return INVISIBLE.sub("", text or "").strip()


def mobile_number(chunk: str) -> str:
    """The chunk as an international mobile number (+263771234567), or ""
    when it isn't one WhatsApp can reach: Zimbabwe landlines and short
    extension fragments like "/ 5" are skipped."""
    digits = re.sub(r"\D", "", chunk)
    if digits.startswith("00"):
        digits = digits[2:]
    if re.fullmatch(r"07[1378]\d{7}", digits):
        digits = "263" + digits[1:]
    elif re.fullmatch(r"7[1378]\d{7}", digits):
        digits = "263" + digits
    if re.fullmatch(r"2637[1378]\d{7}", digits) or re.fullmatch(r"27[678]\d{8}", digits) or re.fullmatch(r"447\d{9}", digits):
        return "+" + digits
    return ""


def first_mobile(text: str) -> str:
    for chunk in CHUNK_SPLIT.split(clean(text)):
        number = mobile_number(chunk)
        if number:
            return number
    return ""


def first_number_digits(text: str) -> str:
    """Digits of the first plausible phone number in a field that may hold
    several -- never all of them run together."""
    text = clean(text)
    mobile = first_mobile(text)
    if mobile:
        return mobile.lstrip("+")
    for chunk in CHUNK_SPLIT.split(text):
        digits = re.sub(r"\D", "", chunk)
        if len(digits) >= 9:
            return digits
    return ""


@dataclass
class ContactParts:
    name: str
    phone: str
    whatsapp: str
    email: str


def split_contact_text(*sources: str) -> ContactParts:
    """Name, readable phone list, first WhatsApp-reachable mobile and first
    email from one or more free-text contact cells."""
    raw = "; ".join(clean(s) for s in sources if clean(s))
    emails = EMAIL.findall(raw)
    person = PERSON.match(raw)
    name = re.sub(r"\s+", " ", person.group(1)).strip() if person else ""

    phone = EMAIL.sub("", raw)
    if name:
        phone = phone.replace(person.group(1), "", 1)
    # Words are notes ("Institutional contacts", "listed in ..."), not numbers.
    phone = re.sub(r"[A-Za-z][A-Za-z.'()-]*", "", phone)
    parts, seen = [], set()
    for part in re.split(r"\s*;\s*", phone):
        part = re.sub(r"\s+", " ", part).strip(" ,/.-:")
        if len(re.sub(r"\D", "", part)) >= 5 and part not in seen:
            seen.add(part)
            parts.append(part)
    phone = "; ".join(parts)

    whatsapp = first_mobile(phone)
    if not name:
        name = UNNAMED if (phone or emails) else NOT_IDENTIFIED
    return ContactParts(name=name, phone=phone, whatsapp=whatsapp, email=emails[0] if emails else "")


def looks_like_contact_text(full_name: str) -> bool:
    """A full_name that is really numbers, an email or a note about the contact."""
    text = clean(full_name)
    if text in (UNNAMED, NOT_IDENTIFIED):
        return False  # already tidied
    return bool(re.search(r"\d{3}|@", text)) or bool(
        re.search(r"\b(contacts?|institutional|to verify|not visible)\b", text, re.I)
    )
