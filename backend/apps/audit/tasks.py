"""Celery Beat schedule for the daily test/pilot-data smell check (apps/audit/services.py) -- the automated
side of the 2026-09-22 cleanup: same checks, run once a day, emailed to the PI admins rather than requiring
someone to remember to run the management command. Read-only; never changes anything.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import Role, User

from .services import test_data_smells

logger = logging.getLogger(__name__)


def _report_body(sections: list[tuple[str, list[str]]]) -> str:
    if not sections:
        return "No test/pilot-data smells found today. Nothing to review."
    lines = ["The following look like test or pilot data, not real fieldwork. Nothing has been changed -- please review:"]
    for title, items in sections:
        lines.append(f"\n{title} ({len(items)}):")
        lines.extend(f"  - {item}" for item in items)
    lines.append(
        "\nRun `manage.py check_test_data_smells` on the server for the same check on demand, "
        "with an optional --since YYYY-MM-DD to limit it to recent records."
    )
    return "\n".join(lines)


@shared_task
def check_test_data_smells_task() -> None:
    recipients = list(
        User.objects.filter(role__name=Role.PI_ADMIN, is_active=True).exclude(email="").values_list("email", flat=True)
    )
    if not recipients:
        logger.warning("check_test_data_smells_task: no active PI_ADMIN with an email address; nothing sent.")
        return
    sections = test_data_smells()
    total = sum(len(lines) for _, lines in sections)
    subject = f"ABF-FST portal: {total} test-data item(s) to review" if total else "ABF-FST portal: no test-data smells today"
    send_mail(subject, _report_body(sections), settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
