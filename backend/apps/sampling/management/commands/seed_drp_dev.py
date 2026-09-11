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

        Respondent.objects.get_or_create(
            sample_case=main_case,
            full_name="E2E Test Respondent",
            defaults={"role_category": RoleCategory.CEO_MD, "is_eligible": True},
        )

        self.stdout.write(self.style.SUCCESS("E2E fixtures seeded:"))
        self.stdout.write(f"  admin username: {E2E_ADMIN_USERNAME}")
        self.stdout.write(f"  admin password: {E2E_ADMIN_PASSWORD}")
        self.stdout.write(f"  main sample_id: {main_case.sample_id}")
        self.stdout.write(f"  reserve sample_id (LOCKED): {reserve_case.sample_id}")
        self.stdout.write(f"  raw invitation token: {raw_token}")
