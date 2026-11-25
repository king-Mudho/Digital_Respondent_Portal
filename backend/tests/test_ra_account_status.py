"""The PI pauses and reactivates research assistants from the Research assistants screen (25 Nov 2026).

The PI deactivated the call RAs who weren't contacting organisations; they contact him to be reactivated. Under test:
only the PI may do it (the Field Coordinator and Supervisor reach the screen but are refused), a reason is required
and both directions are audited, a paused account is listed apart with when and why, and an RA still holding open work
cannot be paused -- that work would sit where nobody can sign in to call it.
"""

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent

from .test_research_assistants import _client, _user, team, work  # noqa: F401  (fixtures)


def _status(client, ra, active, reason="PI decision"):
    return client.post(f"/api/v1/ra/accounts/{ra.id}/status/", {"active": active, "reason": reason}, format="json")


def test_the_pi_pauses_an_ra_with_no_open_work_and_it_is_listed_in_paused(team, work):
    tino = team["tino"]
    work["other_main"].assigned_ra = None
    work["other_main"].save(update_fields=["assigned_ra"])
    resp = _status(_client(team["pi"]), tino, False, "Not contacting organisations")
    assert resp.status_code == 200, resp.json()
    tino.refresh_from_db()
    assert tino.is_active is False
    ev = AuditEvent.objects.get(action="accounts.user_deactivated", object_id=str(tino.pk))
    assert ev.metadata["reason"] == "Not contacting organisations" and ev.user == team["pi"]
    body = _client(team["pi"]).get("/api/v1/ra/team/").json()
    assert tino.id not in [m["id"] for m in body["team"]]
    paused = {p["id"]: p for p in body["paused"]}
    assert paused[tino.id]["paused_reason"] == "Not contacting organisations"
    assert body["can_change_status"] is True


def test_the_pi_reactivates_a_paused_ra_and_they_are_back_on_the_team(team, work):
    tino = team["tino"]
    tino.is_active = False
    tino.save(update_fields=["is_active"])
    resp = _status(_client(team["pi"]), tino, True, "Contacted the PI, ready to call")
    assert resp.status_code == 200
    tino.refresh_from_db()
    assert tino.is_active is True
    assert AuditEvent.objects.filter(action="accounts.user_reactivated", object_id=str(tino.pk)).exists()
    body = _client(team["pi"]).get("/api/v1/ra/team/").json()
    assert tino.id in [m["id"] for m in body["team"]] and tino.id not in [p["id"] for p in body["paused"]]


def test_an_ra_holding_open_work_cannot_be_paused(team, work):
    resp = _status(_client(team["pi"]), team["rudo"], False)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "has_open_work"
    team["rudo"].refresh_from_db()
    assert team["rudo"].is_active is True


def test_only_the_pi_changes_an_account(team, work):
    sup = _user(Role.SUPERVISOR_READONLY, "ra_sup")
    tino = team["tino"]
    tino.is_active = False
    tino.save(update_fields=["is_active"])
    for who in (team["fc"], sup, team["rudo"]):
        assert _status(_client(who), tino, True).status_code == 403, who.username
    tino.refresh_from_db()
    assert tino.is_active is False
    assert _client(team["fc"]).get("/api/v1/ra/team/").json()["can_change_status"] is False


def test_a_reason_is_required_and_only_ra_accounts_can_be_changed(team, work):
    tino = team["tino"]
    tino.is_active = False
    tino.save(update_fields=["is_active"])
    assert _status(_client(team["pi"]), tino, True, "  ").status_code == 400
    assert _status(_client(team["pi"]), team["fc"], False).status_code == 404
    assert _status(_client(team["pi"]), tino, False).status_code == 400  # already paused
    assert User.objects.get(pk=tino.pk).is_active is False


def test_my_work_shows_the_pi_the_paused_ras_and_never_an_ra(team, work):
    tino = team["tino"]
    tino.is_active = False
    tino.save(update_fields=["is_active"])
    pi_body = _client(team["pi"]).get("/api/v1/ra/my-work/").json()
    assert tino.id in [p["id"] for p in pi_body["paused"]]
    ra_body = _client(team["rudo"]).get("/api/v1/ra/my-work/").json()
    assert "paused" not in ra_body
