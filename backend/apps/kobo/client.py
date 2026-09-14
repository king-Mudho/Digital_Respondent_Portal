"""
KoboToolbox REST API client.

Minimal by design: this app never re-implements questionnaire branching or
logic -- KoboToolbox is the sole authority for QUAN form logic and capture
(docs/03_SYSTEM_ARCHITECTURE.md). This client only lists submissions for the
reconciliation job (docs/11_KOBOTOOLBOX_INTEGRATION.md).
"""

import requests
from django.conf import settings


class KoboClient:
    def __init__(self, base_url: str | None = None, api_token: str | None = None, asset_uid: str | None = None):
        self.base_url = (base_url or settings.KOBO_API_BASE_URL).rstrip("/")
        self.api_token = api_token or settings.KOBO_API_TOKEN
        self.asset_uid = asset_uid or settings.KOBO_ASSET_UID

    def fetch_submissions(self) -> list[dict]:
        """GET /api/v2/assets/{asset_uid}/data/ -- the full pull that backs
        scheduled reconciliation (never webhook-only, see
        docs/11_KOBOTOOLBOX_INTEGRATION.md).

        The v2 data endpoint is paginated (DRF-style count/next/previous/
        results) once a survey has more submissions than one page. A single
        unpaginated GET silently returned only the first page forever --
        reconciliation would never see any submission beyond it. This
        follows `next` until Kobo reports no further page.
        """
        headers = {"Authorization": f"Token {self.api_token}"}
        url = f"{self.base_url}/api/v2/assets/{self.asset_uid}/data/"
        results: list[dict] = []
        while url:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            body = response.json()
            results.extend(body.get("results", []))
            url = body.get("next")
        return results

    def fetch_form_survey(self) -> list[dict]:
        """The deployed form's XLSForm survey rows (GET /api/v2/assets/{uid}/),
        in form order -- the source of truth for question names and groups."""
        response = requests.get(
            f"{self.base_url}/api/v2/assets/{self.asset_uid}/",
            headers={"Authorization": f"Token {self.api_token}"},
            params={"format": "json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"]["survey"]
