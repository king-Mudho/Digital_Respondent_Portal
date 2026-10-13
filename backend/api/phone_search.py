"""Search by phone number on the registers (PI request, 2026-10-13).

Phone numbers on file are as messy as the registers they came from: "+263 77 212 3456", "0772123456", "(+263) 242
70396175 or 0242 703 961", "0242 703961-5; +263 242 703961/9". So a search box term that looks like a phone number
-- digits and phone punctuation only, at least six digits once the country code (263) or trunk 0 is dropped -- is
also matched against the digits of each number field, wherever they appear: "0772 123 456", "+263772123456" and
"772123456" all find the same record. Anything else is searched exactly as before.
"""

import re

from django.db.models import CharField, F, Func, Q, Value
from rest_framework.filters import SearchFilter

MIN_DIGITS = 6
PHONE_LIKE = re.compile(r"^[\d\s+()\-./]+$")


def phone_core(term: str) -> str:
    """The digits to look for, or "" when `term` is not a phone number."""
    term = (term or "").strip()
    if not PHONE_LIKE.match(term):
        return ""
    digits = re.sub(r"\D", "", term)
    if digits.startswith("263"):
        digits = digits[3:]
    digits = digits.lstrip("0")
    return digits if len(digits) >= MIN_DIGITS else ""


def digits_of(field: str) -> Func:
    return Func(F(field), Value(r"[^0-9]"), Value(""), Value("g"), function="REGEXP_REPLACE", output_field=CharField())


def phone_matches(queryset, fields, core: str):
    """`queryset` narrowed to rows where any of `fields` (paths through relations allowed) contains `core`."""
    names = {field: f"_phone_{i}" for i, field in enumerate(fields)}
    match = Q()
    for name in names.values():
        match |= Q(**{f"{name}__contains": core})
    return queryset.annotate(**{name: digits_of(field) for field, name in names.items()}).filter(match)


class PhoneSearchFilter(SearchFilter):
    """SearchFilter that also finds rows by phone number. The view names its number fields in `phone_search_fields`;
    the result is whatever the ordinary search finds plus the phone matches, in the view's own order."""

    def filter_queryset(self, request, queryset, view):
        found = super().filter_queryset(request, queryset, view)
        fields = getattr(view, "phone_search_fields", None)
        core = phone_core(request.query_params.get(self.search_param, "")) if fields else ""
        if not core:
            return found
        by_phone = phone_matches(queryset, fields, core).values("pk")
        return queryset.filter(Q(pk__in=found.values("pk")) | Q(pk__in=by_phone))
