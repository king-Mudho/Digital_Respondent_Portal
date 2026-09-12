"""
Dev/E2E fixture seed -- referenced by the root README quick-start
(`python manage.py seed_drp_dev`) and by the Playwright E2E suite
(docs/22_TESTING_STRATEGY.md) for deterministic test data. Synthetic/test
records only -- never run against a production database (mirrors the
sibling ABI project's seed_abi_v01 convention, and the explicit "test
asset/synthetic cases only" rule for dev/staging in
docs/23_DEPLOYMENT_ARCHITECTURE.md).
"""

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.services import issue_invitation
from apps.sampling.models import (
    ActorFamily,
    EntityType,
    Organisation,
    Province,
    ReserveStatus,
    SampleCase,
    SampleType,
    SizeClass,
    StratumDefinition,
    ValueChain,
    WorkflowStatus,
)
from apps.sampling.services import create_organisation, create_sample_case, transition_workflow_status

E2E_ADMIN_USERNAME = "e2e_admin"
E2E_ADMIN_PASSWORD = "E2eDevPassword123!"


class Command(BaseCommand):
    help = "Seed synthetic/test fixtures for local development and the Playwright E2E suite. Never run against production."

    def handle(self, *args, **options):
        for role_name, _ in Role.NAME_CHOICES:
            Role.objects.get_or_create(name=role_name)

        admin_role = Role.objects.get(name=Role.PI_ADMIN)
        admin_user, created = User.objects.get_or_create(
            username=E2E_ADMIN_USERNAME,
            defaults={"role": admin_role, "is_staff": True, "password": make_password(E2E_ADMIN_PASSWORD)},
        )
        if not created:
            admin_user.password = make_password(E2E_ADMIN_PASSWORD)
            admin_user.role = admin_role
            admin_user.save(update_fields=["password", "role"])

        stratum, _ = StratumDefinition.objects.get_or_create(
            code="E2E-HA-PRODUCER-HORTICULTURE-SMALL",
            defaults=dict(
                province=Province.HARARE, actor_family=ActorFamily.PRODUCER_FARMER,
                value_chain=ValueChain.HORTICULTURE, size_class=SizeClass.SMALL, target_count=10,
            ),
        )

        org = Organisation.objects.filter(name="E2E Test Farming Trust").first()
        if org is None:
            org = create_organisation(
                province=Province.HARARE, name="E2E Test Farming Trust",
                entity_type=EntityType.COOPERATIVE, district="Harare",
                actor_family=ActorFamily.PRODUCER_FARMER, value_chain=ValueChain.HORTICULTURE,
                size_class=SizeClass.SMALL,
            )

        main_case = SampleCase.objects.filter(organisation=org, sample_type=SampleType.MAIN).first()
        if main_case is None:
            main_case = create_sample_case(organisation=org, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
            for status in [
                WorkflowStatus.S01_VERIFICATION_REQUIRED,
                WorkflowStatus.S02_ORGANISATION_VERIFIED,
                WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED,
            ]:
                transition_workflow_status(main_case, status)

        raw_token, _, _ = issue_invitation(main_case)

        reserve_org = Organisation.objects.filter(name="E2E Locked Reserve Trust").first()
        if reserve_org is None:
            reserve_org = create_organisation(
                province=Province.HARARE, name="E2E Locked Reserve Trust",
                entity_type=EntityType.COOPERATIVE, district="Harare",
                actor_family=ActorFamily.PRODUCER_FARMER, value_chain=ValueChain.HORTICULTURE,
                size_class=SizeClass.SMALL,
            )
        reserve_case = SampleCase.objects.filter(organisation=reserve_org, sample_type=SampleType.RESERVE).first()
        if reserve_case is None:
            reserve_case = create_sample_case(
                organisation=reserve_org, stratum=stratum, sample_type=SampleType.RESERVE, year=2026
            )
        main_case.matched_case = reserve_case
        main_case.save(update_fields=["matched_case"])

        # Force LOCKED on every run -- reserve-lock.spec.ts asserts this
        # case is never invitable, but nothing stops a manual QA session
        # (e.g. against /admin/reserve) from activating it in a shared,
        # never-reset local database. This fixture's entire purpose is to
        # stay locked; a stray manual activation should never be able to
        # make reserve-lock.spec.ts fail on the next run.
        reserve_case.status = ReserveStatus.LOCKED
        reserve_case.activation_reason = ""
        reserve_case.activated_by = None
        reserve_case.activated_at = None
        reserve_case.activation_evidence_note = ""
        reserve_case.save(update_fields=[
            "status", "activation_reason", "activated_by", "activated_at", "activation_evidence_note",
        ])

        Respondent.objects.get_or_create(
            sample_case=main_case,
            full_name="E2E Test Respondent",
            defaults={"role_category": RoleCategory.CEO_MD, "is_eligible": True},
        )

        # A second, dedicated LOCKED reserve case, matched to its own main
        # case -- kept separate from reserve_case above because
        # reserve-lock.spec.ts asserts that one stays LOCKED for the whole
        # suite run. The admin-reserve-activation E2E spec activates this
        # one instead, so activating it can never make reserve-lock.spec.ts
        # flaky depending on test execution order.
        activation_main_org = Organisation.objects.filter(name="E2E Activation Main Trust").first()
        if activation_main_org is None:
            activation_main_org = create_organisation(
                province=Province.HARARE, name="E2E Activation Main Trust",
                entity_type=EntityType.COOPERATIVE, district="Harare",
                actor_family=ActorFamily.PRODUCER_FARMER, value_chain=ValueChain.HORTICULTURE,
                size_class=SizeClass.SMALL,
            )
        activation_main_case = SampleCase.objects.filter(
            organisation=activation_main_org, sample_type=SampleType.MAIN
        ).first()
        if activation_main_case is None:
            activation_main_case = create_sample_case(
                organisation=activation_main_org, stratum=stratum, sample_type=SampleType.MAIN, year=2026
            )

        activation_reserve_org = Organisation.objects.filter(name="E2E Activation Reserve Trust").first()
        if activation_reserve_org is None:
            activation_reserve_org = create_organisation(
                province=Province.HARARE, name="E2E Activation Reserve Trust",
                entity_type=EntityType.COOPERATIVE, district="Harare",
                actor_family=ActorFamily.PRODUCER_FARMER, value_chain=ValueChain.HORTICULTURE,
                size_class=SizeClass.SMALL,
            )
        activation_reserve_case = SampleCase.objects.filter(
            organisation=activation_reserve_org, sample_type=SampleType.RESERVE
        ).first()
        if activation_reserve_case is None:
            activation_reserve_case = create_sample_case(
                organisation=activation_reserve_org, stratum=stratum, sample_type=SampleType.RESERVE, year=2026
            )
        activation_main_case.matched_case = activation_reserve_case
        activation_main_case.save(update_fields=["matched_case"])

        # Force LOCKED every run (not just on first creation) -- this
        # fixture's whole purpose is to be repeatedly activated by
        # admin-reserve-activation.spec.ts, so re-running this command
        # without a fresh database must always hand back a locked case,
        # never one left ACTIVATED by a prior run.
        activation_reserve_case.status = ReserveStatus.LOCKED
        activation_reserve_case.activation_reason = ""
        activation_reserve_case.activated_by = None
        activation_reserve_case.activated_at = None
        activation_reserve_case.activation_evidence_note = ""
        activation_reserve_case.save(update_fields=[
            "status", "activation_reason", "activated_by", "activated_at", "activation_evidence_note",
        ])

        # A third, dedicated main case for admin-workflow-and-contact-
        # log.spec.ts's transition-button test. Kept separate from
        # main_case above, which every invitation-flow spec re-invites
        # (issue_invitation() auto-advances a case's workflow_status, e.g.
        # S03 -> S05) and which a workflow-transition test would eventually
        # push to a terminal status with no transitions left after enough
        # repeated runs. Force-reset to S03 on every seed run,
        # bypassing the state machine directly (same pattern as the
        # reserve-activation fixture's LOCKED reset above), so this test
        # always has at least one transition available regardless of how
        # many times it has already run against this database.
        workflow_test_org = Organisation.objects.filter(name="E2E Workflow Transition Trust").first()
        if workflow_test_org is None:
            workflow_test_org = create_organisation(
                province=Province.HARARE, name="E2E Workflow Transition Trust",
                entity_type=EntityType.COOPERATIVE, district="Harare",
                actor_family=ActorFamily.PRODUCER_FARMER, value_chain=ValueChain.HORTICULTURE,
                size_class=SizeClass.SMALL,
            )
        workflow_test_case = SampleCase.objects.filter(
            organisation=workflow_test_org, sample_type=SampleType.MAIN
        ).first()
        if workflow_test_case is None:
            workflow_test_case = create_sample_case(
                organisation=workflow_test_org, stratum=stratum, sample_type=SampleType.MAIN, year=2026
            )
        workflow_test_case.workflow_status = WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED
        workflow_test_case.save(update_fields=["workflow_status"])

        self.stdout.write(self.style.SUCCESS("E2E fixtures seeded:"))
        self.stdout.write(f"  admin username: {E2E_ADMIN_USERNAME}")
        self.stdout.write(f"  admin password: {E2E_ADMIN_PASSWORD}")
        self.stdout.write(f"  main sample_id: {main_case.sample_id}")
        self.stdout.write(f"  reserve sample_id (LOCKED): {reserve_case.sample_id}")
        self.stdout.write(f"  activation reserve sample_id (LOCKED): {activation_reserve_case.sample_id}")
        self.stdout.write(f"  workflow transition test sample_id: {workflow_test_case.sample_id}")
        self.stdout.write(f"  raw invitation token: {raw_token}")
