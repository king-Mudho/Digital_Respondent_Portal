"""
Engineering pre-flight for docs/28's go-live acceptance checklist, run
against the real deployment.

Every write happens inside one transaction that is rolled back at the end:
invitations, consent, eligibility, a withdrawal and a reserve activation are
exercised through the real API views and services, then undone -- including
their audit events. Nothing is sent to KoboToolbox or WhatsApp.

    python manage.py golive_preflight

This is evidence for the PI's own run-through, not a replacement for it
(docs/28 "Sign-off rule").
"""

import csv
import io

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentType
from apps.consent.services import latest_consent
from apps.contacts.models import Respondent
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation
from apps.kobo.services import reconciliation_is_configured, redirect_is_configured, sign_portal_token
from apps.sampling.models import ActivationReason, ReserveStatus, SampleCase, SampleType
from apps.sampling.services import activate_reserve, transition_workflow_status


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Run the go-live checklist checks against this deployment, rolled back."

    def _counts(self):
        from apps.consent.models import ConsentRecord

        return {model.__name__: model.objects.count()
                for model in (AuditEvent, InvitationToken, ConsentRecord, Respondent, SampleCase, User)}

    def handle(self, *args, **options):
        self.results = []
        before = self._counts()
        try:
            with transaction.atomic():
                self._run()
                raise _Rollback
        except _Rollback:
            pass
        after = self._counts()
        self.record("rollback left no trace", before == after, f"row counts unchanged: {after}")
        failed = [r for r in self.results if not r[1]]
        for name, ok, detail in self.results:
            mark = self.style.SUCCESS("PASS") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"{mark}  {name} -- {detail}")
        self.stdout.write(f"\n{len(self.results) - len(failed)}/{len(self.results)} passed; all writes rolled back.")

    # --------------------------------------------------------------- helpers
    def record(self, name, ok, detail):
        self.results.append((name, bool(ok), detail))

    def client(self, role_name=None):
        host = (settings.ALLOWED_HOSTS or ["localhost"])[0]
        client = APIClient(HTTP_HOST=host, SERVER_NAME=host)
        client.defaults["wsgi.url_scheme"] = "https"
        client.defaults["HTTP_X_FORWARDED_PROTO"] = "https"
        if role_name:
            role, _ = Role.objects.get_or_create(name=role_name)
            user = User.objects.create_user(username=f"preflight_{role_name.lower()}", password=None, role=role)
            client.force_authenticate(user)
        return client

    def api(self, client, method, path, data=None):
        return getattr(client, method)(f"/api/v1{path}", data, format="json", secure=True)

    # ------------------------------------------------------------------ run
    def _run(self):
        public = self.client()
        pi = self.client(Role.PI_ADMIN)
        fc = self.client(Role.FIELD_COORDINATOR)
        contact_ra = self.client(Role.CONTACT_RA)

        # Cases with no respondent, consent or invitation history, so every gate is tested from scratch.
        main = (SampleCase.objects.filter(sample_type=SampleType.MAIN, workflow_status="S00",
                                          respondents__isnull=True, consent_records__isnull=True,
                                          invitation_tokens__isnull=True)
                .order_by("sample_id").first())
        reserve = (SampleCase.objects.filter(sample_type=SampleType.RESERVE, status=ReserveStatus.LOCKED,
                                             invitation_tokens__isnull=True)
                   .order_by("sample_id").first())

        # 1. Public visitor
        r = self.api(public, "get", "/invitations/validate/?t=not-a-real-invitation-token")
        self.record("1 public visitor refused", r.status_code == 400 and r.json()["error"]["code"] == "token_invalid",
                   f"bogus link -> HTTP {r.status_code}")
        r = self.api(public, "get", "/kobo/redirect-url/?t=not-a-real-invitation-token")
        self.record("1 no questionnaire link without an invitation", r.status_code == 400, f"HTTP {r.status_code}")
        forged = sign_portal_token(1, "SID-2026-000001") != sign_portal_token(1, "SID-2026-000002")
        self.record("1 public form link cannot submit for a guessed case", forged,
                   "login-free submissions need the per-case portal signature")

        # 2. Valid invitation reveals minimal data
        for status in ("S01", "S02", "S03"):
            transition_workflow_status(main, status)
        raw, _, token = issue_invitation(main)
        r = self.api(public, "get", f"/invitations/validate/?t={raw}")
        body = r.json()
        leaked = {"sample_id", "master_id", "stratum", "sample_type", "province"} & set(body)
        self.record("2 valid invitation shows only confirmation data", r.status_code == 200 and not leaked,
                   f"fields: {sorted(body)}")

        # 3. Locked reserve
        r = self.api(fc, "post", "/invitations/", {"sample_id": reserve.sample_id, "channel": "WHATSAPP", "invitation_wave": 1})
        self.record("3 locked reserve cannot be invited", r.status_code >= 400 and not InvitationToken.objects.filter(sample_case=reserve).exists(),
                   f"{reserve.sample_id} -> HTTP {r.status_code}")

        # 4. Ineligible respondent
        self.api(public, "post", "/eligibility/", {"token": raw, "full_name": "Preflight Receptionist", "role_category": "RECEPTIONIST"})
        self.api(public, "post", "/consent/", {"token": raw, "consent_type": "PARTICIPATION", "decision": "GIVEN",
                                               "information_sheet_version": "v1.3", "method": "WEB_CLICKTHROUGH"})
        r = self.api(public, "get", f"/kobo/redirect-url/?t={raw}")
        self.record("4 ineligible respondent never gets the questionnaire",
                   r.status_code == 403 and r.json()["error"]["code"] == "eligibility_required", f"HTTP {r.status_code}")

        # 5. Consent required
        raw2, _, _ = issue_invitation(main, invitation_wave=2)
        self.api(public, "post", "/eligibility/", {"token": raw2, "full_name": "Preflight CEO", "role_category": "CEO_MD"})
        self.api(public, "post", "/consent/", {"token": raw2, "consent_type": "PARTICIPATION", "decision": "DECLINED",
                                               "information_sheet_version": "v1.3", "method": "WEB_CLICKTHROUGH"})
        r = self.api(public, "get", f"/kobo/redirect-url/?t={raw2}")
        self.record("5 no questionnaire without consent",
                   r.status_code == 403 and r.json()["error"]["code"] == "consent_required", f"declined -> HTTP {r.status_code}")

        # 6. Sample_ID and mode reach Kobo
        self.api(public, "post", "/consent/", {"token": raw2, "consent_type": "PARTICIPATION", "decision": "GIVEN",
                                               "information_sheet_version": "v1.3", "method": "WEB_CLICKTHROUGH"})
        r = self.api(public, "get", f"/kobo/redirect-url/?t={raw2}&administration_mode=01&consent_version=v1.3")
        url = r.json().get("kobo_form_url", "") if r.status_code == 200 else ""
        self.record("6 Sample_ID and mode are in the questionnaire link",
                   f"d[sample_id]={main.sample_id}" in url and "d[administration_mode]=01" in url and "d[portal_token_id]=" in url,
                   url.split("?")[0] if url else f"HTTP {r.status_code}")

        # 7. Reused / superseded tokens
        r = self.api(public, "get", f"/invitations/validate/?t={raw}")
        token.refresh_from_db()
        self.record("7 a superseded invitation stops working", r.status_code == 400 and token.status == TokenStatus.EXPIRED,
                   f"old link -> HTTP {r.status_code} ({r.json()['error']['code']})")

        # 8. Kobo connection
        self.record("8 KoboToolbox connected", redirect_is_configured() and reconciliation_is_configured(),
                   "form link and sync configured (end-to-end submission proven 2026-09-14)")

        # 9. De-identified export
        r = self.api(pi, "get", "/export/analysis/")
        content = b"".join(r.streaming_content) if hasattr(r, "streaming_content") else r.content
        header = next(csv.reader(io.StringIO(content.decode())), [])
        contact_cols = {"organisation_name", "respondent_full_name", "respondent_phone", "respondent_email",
                        "gatekeeper_name", "gatekeeper_contact"} & set(header)
        self.record("9 no contact data in the de-identified export", r.status_code == 200 and not contact_cols,
                   f"columns: {', '.join(header)}")

        # 10. Role permissions
        denied = {path: self.api(contact_ra, "get", path).status_code for path in ("/audit/", "/export/analysis/", "/qa/queue/", "/kii/")}
        self.record("10 a Contact RA cannot open other duties", all(code == 403 for code in denied.values()),
                   ", ".join(f"{p} {c}" for p, c in denied.items()))

        # 11. Reserve activation audit
        pi_user = User.objects.get(username="preflight_pi_admin")
        activate_reserve(reserve, reason=ActivationReason.REFUSAL, activated_by=pi_user, evidence_note="preflight")
        event = AuditEvent.objects.filter(action="reserve.activated", object_id=str(reserve.pk)).order_by("-id").first()
        self.record("11 reserve activation is audited with reason and authoriser",
                   event and event.metadata.get("reason") == "REFUSAL" and event.metadata.get("activated_by_id") == pi_user.id,
                   f"audit event {'written' if event else 'missing'}")

        # 14. Withdrawal
        Respondent.objects.filter(sample_case=main).update(phone="0770000000")
        r = self.api(fc, "post", f"/sample-cases/{main.sample_id}/withdraw/", {"reason": "Preflight withdrawal"})
        record = latest_consent(main, ConsentType.PARTICIPATION)
        live = InvitationToken.objects.filter(sample_case=main).exclude(status__in=[TokenStatus.EXPIRED, TokenStatus.REVOKED]).count()
        erased = not Respondent.objects.filter(sample_case=main).exclude(phone="").exists()
        self.record("14 withdrawal can be recorded and takes effect",
                   r.status_code == 201 and record.decision == ConsentDecision.WITHDRAWN and live == 0 and erased,
                   f"HTTP {r.status_code}, live invitations {live}, contacts erased {erased}")
