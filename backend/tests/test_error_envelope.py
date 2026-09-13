"""
The uniform error envelope (docs/06_API_ARCHITECTURE.md) must carry a
usable `message`, not only `field_errors`.

Found during the respondent-flow audit: a DRF ValidationError has no
top-level "detail", so every validation failure came back as
{"code": "invalid", "message": "An error occurred.", "field_errors": {...}}.
The respondent flow has no field-level error UI -- it shows `message` --
so a respondent whose input the API could describe precisely was told
only that "an error occurred".
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.invitations.services import issue_invitation


@pytest.fixture
def client():
    return APIClient()


def test_validation_error_message_names_the_actual_problem(client, main_case):
    raw_token, _, _ = issue_invitation(main_case)
    past = (timezone.now() - timezone.timedelta(days=30)).isoformat()

    response = client.post(
        "/api/v1/appointments/", {"token": raw_token, "scheduled_for": past, "mode": "PHONE"}, format="json"
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["message"] == "An appointment cannot be requested in the past."
    # field_errors is still populated for callers that render per field.
    assert "scheduled_for" in error["field_errors"]


def test_non_validation_errors_keep_their_own_detail(client):
    """A 404/permission error already has a top-level "detail" -- that must
    still win over anything in field_errors."""
    response = client.get("/api/v1/audit/")

    assert response.status_code in (401, 403)
    assert response.json()["error"]["message"] != "An error occurred."
