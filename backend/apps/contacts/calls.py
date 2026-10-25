"""
Calls (PI, 25 Oct 2026): everyone whose link was sent but who has not finished, with every contact on file, so a
person can phone them -- Main 400 (including activated reserves) and KII, filtered by how far each got. A call is
logged as a ContactEvent (channel PHONE) on the case or KII record, so it sits in the same contact-attempt log as
every other attempt.

Who sees what is the Communications rule, reused rather than re-derived: PI, Field Coordinator and Supervisor see
both studies; a Contact RA only their assigned Main-400 cases; a KII RA only KII records
(messaging.communications.visible_cases / visible_records). The permission class (api.permissions.CanUseCalls)
decides who may open the screen at all; these querysets decide which rows.
"""

import re

from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.audit.utils import log_action
from apps.invitations.models import InvitationToken
from apps.kii.models import KIIInvitationToken
from apps.messaging.communications import visible_cases, visible_records
from apps.messaging.models import MessagePurpose, ProviderMessage

from .models import ContactChannel, ContactEvent, ContactOutcome

STAGE_LABELS = {
    "started": "Started, not finished",
    "consented": "Consented, not started",
    "opened": "Opened, not started",
    "not_opened": "Link sent, not opened",
}
STAGE_ORDER = list(STAGE_LABELS)
# How far a live link got, per study. A link that is submitted, QA-passed, expired or revoked is not a call.
MAIN_STAGE = {"SURVEY_STARTED": "started", "CONSENTED": "consented", "ELIGIBILITY_PASSED": "consented",
              "OPENED": "opened", "SENT": "not_opened", "GENERATED": "not_opened"}
KII_STAGE = {"STARTED": "started", "CONSENTED": "consented", "OPENED": "opened", "SENT": "not_opened",
             "GENERATED": "not_opened"}
FINISHED = ("SUBMITTED", "QA_PASSED")


class CallError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def _numbers(*values) -> list[str]:
    """Every distinct phone number in these fields ("0771 234 567; +263 77 765 4321" holds two)."""
    out = []
    for value in values:
        for part in re.split(r"[;,/\n]+", value or ""):
            part = part.strip()
            if sum(ch.isdigit() for ch in part) >= 7 and part not in out:
                out.append(part)
    return out


def _whatsapp_link(number: str) -> str:
    from apps.messaging.services import whatsapp_digits

    digits = whatsapp_digits(number)
    return f"https://wa.me/{digits}" if digits else ""


def _person(name, role, numbers, email, gatekeeper=""):
    return {"name": name, "role": role, "email": email or "", "gatekeeper": gatekeeper,
            "numbers": [{"number": n, "whatsapp_link": _whatsapp_link(n)} for n in numbers]}


def _when(value):
    return value.isoformat() if value else None


def _last_call(events):
    calls = [e for e in events if e.channel == ContactChannel.PHONE]
    if not calls:
        return None, 0
    e = calls[0]  # ContactEvent.Meta.ordering is -occurred_at
    return {"at": _when(e.occurred_at), "outcome": e.outcome, "outcome_label": e.get_outcome_display(), "notes": e.notes,
            "by": e.ra.get_full_name() or e.ra.username, "next_action_date": _when(e.next_action_date)}, len(calls)


def _reminder_counts(field: str, ids) -> dict:
    rows = (ProviderMessage.objects.filter(**{f"{field}__in": ids}, purpose=MessagePurpose.REMINDER)
            .values(field).annotate(n=Count("id")))
    return {r[field]: r["n"] for r in rows}


def _main_items(user):
    from apps.sampling.models import SampleType

    events = Prefetch("contact_events", queryset=ContactEvent.objects.select_related("ra"))
    cases = (visible_cases(user)
             .filter(Q(sample_type=SampleType.MAIN, workflow_status__in=["S05", "S06", "S07"])
                     | Q(sample_type=SampleType.RESERVE, status="ACTIVATED"))
             .exclude(metadata__has_key="duplicate_of")
             .exclude(invitation_tokens__status__in=FINISHED)
             .filter(invitation_tokens__status__in=MAIN_STAGE)
             .distinct()
             .prefetch_related("respondents", events,
                               Prefetch("invitation_tokens", queryset=InvitationToken.objects.filter(status__in=MAIN_STAGE))))
    cases = list(cases)
    reminders = _reminder_counts("sample_case_id", [c.id for c in cases])
    for c in cases:
        tokens = list(c.invitation_tokens.all())
        token = min(tokens, key=lambda t: STAGE_ORDER.index(MAIN_STAGE[t.status]))
        org = c.organisation
        people = [_person(p.full_name, p.get_role_category_display() if p.role_category else "",
                          _numbers(p.whatsapp_number, p.phone, p.gatekeeper_contact if not p.gatekeeper_name else ""),
                          p.email, " ".join(x for x in (p.gatekeeper_name, p.gatekeeper_contact) if x))
                  for p in c.respondents.all()]
        last, n_calls = _last_call(list(c.contact_events.all()))
        yield {
            "kind": "main", "id": c.sample_id, "study": "Main 400" + (" reserve" if c.sample_type == SampleType.RESERVE else ""),
            "organisation": org.name, "location": ", ".join(x for x in (org.district, org.get_province_display()) if x),
            "sector": org.get_actor_family_display(), "stage": MAIN_STAGE[token.status],
            "link_sent": _when(token.issued_at), "link_opened": _when(token.first_opened_at), "link_expires": _when(token.expires_at),
            "link_channel": token.get_channel_display(), "people": people,
            "public_contacts": str((org.metadata or {}).get("public_contacts") or ""),
            "reminders": reminders.get(c.id, 0), "calls": n_calls, "last_call": last, "detail_path": f"/admin/sample/{c.sample_id}",
        }


def _kii_items(user):
    from apps.contacts.kii_finder import is_placeholder, organisation_name

    events = Prefetch("contact_events", queryset=ContactEvent.objects.select_related("ra"))
    records = list(visible_records(user).filter(status="INVITED", invitation_tokens__status__in=KII_STAGE).distinct()
                   .select_related("organisation")
                   .prefetch_related(events, Prefetch("invitation_tokens", queryset=KIIInvitationToken.objects.filter(status__in=KII_STAGE))))
    reminders = _reminder_counts("kii_record_id", [r.id for r in records])
    pools = {"CORE_60": "Core 60", "RESERVE_30": "Reserve 30", "ADDITIONAL": "Additional"}
    for r in records:
        tokens = list(r.invitation_tokens.all())
        token = min(tokens, key=lambda t: STAGE_ORDER.index(KII_STAGE[t.status]))
        meta, org = r.metadata or {}, r.organisation
        name = "" if is_placeholder(r) else r.participant_name
        last, n_calls = _last_call(list(r.contact_events.all()))
        yield {
            "kind": "kii", "id": r.kii_id, "study": "KII " + pools.get(meta.get("pool"), "").strip(),
            "organisation": organisation_name(r), "location": ", ".join(x for x in ((org.district, org.get_province_display()) if org else ()) if x),
            "sector": r.stakeholder_category, "stage": KII_STAGE[token.status],
            "link_sent": _when(token.issued_at), "link_opened": _when(token.first_opened_at), "link_expires": _when(token.expires_at),
            "link_channel": token.get_channel_display(),
            "people": [_person(name, r.participant_role, _numbers(r.whatsapp_number, r.phone), r.email)],
            "public_contacts": str(meta.get("public_contacts") or ""),
            "reminders": reminders.get(r.id, 0), "calls": n_calls, "last_call": last, "detail_path": f"/admin/kii/{r.pk}",
        }


def call_list(user, *, study: str = "all", stage: str = "all", q: str = "") -> dict:
    """Everyone to call, closest to finishing first (then the oldest link), with counts per study and stage for the
    filters -- counted before the stage filter, so each chip shows what choosing it would list."""
    items = []
    if study in ("all", "main"):
        items += list(_main_items(user))
    if study in ("all", "kii"):
        items += list(_kii_items(user))
    needle = (q or "").strip().lower()
    if needle:
        digits = re.sub(r"\D", "", needle)

        def matches(item):
            text = " ".join([item["id"], item["organisation"], *(p["name"] for p in item["people"])]).lower()
            numbers = "".join(re.sub(r"\D", "", n["number"]) for p in item["people"] for n in p["numbers"])
            return needle in text or (len(digits) >= 4 and digits in numbers)

        items = [i for i in items if matches(i)]
    counts = {s: sum(1 for i in items if i["stage"] == s) for s in STAGE_ORDER}
    if stage in STAGE_LABELS:
        items = [i for i in items if i["stage"] == stage]
    items.sort(key=lambda i: (STAGE_ORDER.index(i["stage"]), i["link_sent"] or "", i["id"]))
    return {
        "results": [{**i, "stage_label": STAGE_LABELS[i["stage"]]} for i in items],
        "count": len(items), "stage_counts": counts, "stage_labels": STAGE_LABELS,
        "studies": [s for s, qs in (("main", visible_cases(user)), ("kii", visible_records(user))) if qs.exists()],
        "outcomes": [{"value": v, "label": label} for v, label in ContactOutcome.choices],
    }


def log_call(user, kind: str, ident: str, *, outcome: str, notes: str = "", next_action_date=None) -> ContactEvent:
    """Record one phone call on a case or KII record the user may see. A refusal is recorded as the call's outcome
    only: moving a case to Refused stays the case page's decision, as before."""
    if kind == "main":
        subject = visible_cases(user).filter(sample_id=ident).first()
    elif kind == "kii":
        subject = visible_records(user).filter(kii_id=ident).first()
    else:
        subject = None
    if subject is None:
        raise CallError("not_found", "That case or record was not found, or is not one you can call.", 404)
    if outcome not in ContactOutcome.values:
        raise CallError("invalid_outcome", "Choose what happened on the call.")
    when = parse_date(next_action_date) if isinstance(next_action_date, str) and next_action_date else next_action_date or None
    if next_action_date and when is None:
        raise CallError("invalid_date", "The call-back date isn't a valid date.")
    event = ContactEvent.objects.create(
        sample_case=subject if kind == "main" else None, kii_record=subject if kind == "kii" else None,
        channel=ContactChannel.PHONE, occurred_at=timezone.now(), outcome=outcome, notes=(notes or "").strip(),
        next_action_date=when, ra=user)
    log_action("contacts.call_logged", subject, {"kind": kind, "id": ident, "outcome": outcome, "event": event.pk,
                                                 "user_id": user.id}, user=user)
    return event
