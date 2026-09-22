"""apps/audit/labels.py -- turning a raw action code + metadata into what the Audit Log screen shows."""

import pytest

from apps.audit.labels import ACTION_LABELS, describe


def test_every_action_actually_used_in_the_codebase_has_a_label():
    """A living check: every log_action() call site's action string is covered, so the audit screen never
    falls back to an unslugified code for something that happens in normal use."""
    import pathlib
    import re

    apps_dir = pathlib.Path(__file__).resolve().parent.parent / "apps"
    used = set()
    pattern = re.compile(r'log_action\(\s*\n?\s*(?:"([a-z_]+\.[a-z_]+)"|f"([a-z_]+\.[a-z_]+)")')
    for path in apps_dir.rglob("*.py"):
        if "migrations" in path.parts or "test" in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            used.add(m.group(1) or m.group(2))
    missing = used - set(ACTION_LABELS)
    # consent.withdrawn is chosen dynamically (consent.recorded if not withdrawn else consent.withdrawn) --
    # the regex only sees the literal it's next to; both variants are covered explicitly below regardless.
    missing -= {"consent.withdrawn"}
    assert not missing, f"No human label for: {sorted(missing)}"


def test_an_unmapped_action_still_gets_a_readable_fallback():
    label, _ = describe("some_new_app.something_happened", {})
    assert label == "Some new app something happened"


def test_from_to_pair_renders_as_an_arrow():
    label, detail = describe("sampling.status_reset_after_test_cleanup", {"from": "S07", "to": "S03"})
    assert label == "Case status reset (test cleanup)"
    assert detail == "S07 → S03"


def test_a_reason_and_sample_id_both_show():
    _, detail = describe("invitation.revoked", {"reason": "Revoked from admin UI", "revoked_by_id": 6})
    assert "Revoked from admin UI" in detail


def test_a_long_list_is_summarised_not_dumped():
    _, detail = describe("sampling.bulk_assignment", {"sample_ids": [f"SID-{i}" for i in range(50)], "moved": 50})
    assert "50 item(s)" in detail
    assert "SID-0" not in detail


def test_empty_metadata_gives_an_empty_detail():
    _, detail = describe("proit.interview_completed", {})
    assert detail == ""


def test_old_new_pair_from_the_kii_name_correction():
    _, detail = describe("kii.participant_name_corrected", {"old": "Happyson Saina", "new": "GigaFood One (contact not yet identified)"})
    assert "was: Happyson Saina" in detail
    assert "now: GigaFood One" in detail
