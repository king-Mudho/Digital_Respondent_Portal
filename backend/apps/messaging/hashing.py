"""Keyed hashes of numbers and email addresses (2026-10-07, email 2026-10-12): enough to recognise a reply or a bounce
from the same person without keeping the number or address itself on a message row."""

import hashlib
import hmac

from django.conf import settings


def _keyed(text: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), text.encode(), hashlib.sha256).hexdigest()


def number_hash(digits: str) -> str:
    """Of a phone number's digits only, so +263 77..., 26377... and 263-77... hash the same."""
    return _keyed("".join(ch for ch in digits or "" if ch.isdigit()))


def email_hash(address: str) -> str:
    return _keyed("email:" + (address or "").strip().lower())


def mask_email(address: str) -> str:
    local, _, domain = (address or "").strip().partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"
