"""
Reserve lock, identifier generation and workflow-transition tests --
docs/22_TESTING_STRATEGY.md marks the reserve lock as "highest priority": a
regression here breaks the study's core integrity guarantee.
"""

import re
import threading

import pytest
from django.db import connection

from apps.sampling.models import (
    Province,
    WorkflowStatus,
)
from apps.sampling.services import (
    InvalidWorkflowTransition,
    generate_master_id,
    is_invitable,
    transition_workflow_status,
)

# --- Reserve lock (docs/22_TESTING_STRATEGY.md "highest priority") --------

def test_locked_reserve_is_not_invitable(locked_reserve_case):
    assert is_invitable(locked_reserve_case) is False


def test_activated_reserve_is_invitable(activated_reserve_case):
    assert is_invitable(activated_reserve_case) is True


def test_main_case_is_always_invitable(main_case):
    assert is_invitable(main_case) is True


# --- Identifier generation -------------------------------------------------

def test_master_id_format(organisation):
    assert re.fullmatch(r"MID-HA-\d{6}", organisation.master_id)


def test_master_id_unique_and_monotonic_within_province(db):
    ids = [
        generate_master_id(Province.HARARE)
        for _ in range(5)
    ]
    assert len(set(ids)) == 5
    sequences = [int(i.split("-")[-1]) for i in ids]
    assert sequences == sorted(sequences)


def test_master_id_sequence_independent_per_province(db):
    first_harare = generate_master_id(Province.HARARE)
    first_bulawayo = generate_master_id(Province.BULAWAYO)
    assert first_harare.split("-")[1] == "HA"
    assert first_bulawayo.split("-")[1] == "BU"


def test_sample_id_format(main_case):
    assert re.fullmatch(r"SID-2026-\d{6}", main_case.sample_id)


@pytest.mark.django_db(transaction=True)
def test_master_id_generation_unique_under_concurrent_import():
    """docs/28_DEFINITION_OF_DONE.md: 'verified unique under a
    concurrent-import test.' Real threads, each with its own DB connection,
    hammering the same province code -- select_for_update() in
    sampling.services.next_sequence must serialise them without a
    duplicate or a lost update.
    """
    results = []
    errors = []

    def worker():
        try:
            results.append(generate_master_id(Province.MASVINGO))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert len(results) == len(set(results)) == 20


# --- Workflow status engine -------------------------------------------------

def test_valid_workflow_transition(main_case):
    updated = transition_workflow_status(main_case, WorkflowStatus.S01_VERIFICATION_REQUIRED)
    assert updated.workflow_status == WorkflowStatus.S01_VERIFICATION_REQUIRED


def test_invalid_workflow_transition_rejected_and_audited(main_case):
    from apps.audit.models import AuditEvent

    with pytest.raises(InvalidWorkflowTransition):
        # S00 cannot jump straight to S08 -- skips verification/consent/etc.
        transition_workflow_status(main_case, WorkflowStatus.S08_SURVEY_SUBMITTED)

    main_case.refresh_from_db()
    assert main_case.workflow_status == WorkflowStatus.S00_SELECTED_MAIN  # unchanged
    assert AuditEvent.objects.filter(action="sampling.invalid_workflow_transition").exists()


def test_reserve_case_cannot_use_workflow_transition(locked_reserve_case):
    with pytest.raises(InvalidWorkflowTransition):
        transition_workflow_status(locked_reserve_case, WorkflowStatus.S01_VERIFICATION_REQUIRED)
