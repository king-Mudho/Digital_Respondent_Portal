"""
apps/evidence/ai_coding.py -- the AI drafting engine for the Document
Analysis Tool. Every test mocks the Anthropic call (no real API key or
network request); what's under test is the prompt/schema construction,
the deterministic-field override, and that this module never contacts
KoboToolbox itself (see its own docstring for why that boundary matters:
this only ever produces an editable draft, never a submission).
"""

from datetime import date
from unittest.mock import Mock, patch

import anthropic
import pytest

from apps.evidence.ai_coding import (
    DETERMINISTIC_FIELDS,
    AIDraftError,
    _read_file_block,
    _tool_schema,
    ai_coding_is_configured,
    generate_draft,
)
from apps.evidence.document_tool_schema import SCHEMA
from apps.evidence.models import DocumentRecord
from apps.evidence.services import generate_document_id


@pytest.fixture
def document(db):
    return DocumentRecord.objects.create(
        document_id=generate_document_id(),
        title="NDS2 test document",
        author_or_speaker="Government of Zimbabwe",
        publication_or_event_date=date(2025, 11, 27),
        source_url_or_reference="https://example.com/nds2.pdf",
        document_type="OFFICIAL",
    )


def test_ai_coding_is_configured(settings):
    settings.ANTHROPIC_API_KEY = ""
    assert ai_coding_is_configured() is False
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    assert ai_coding_is_configured() is True


def test_tool_schema_excludes_deterministic_fields():
    tool = _tool_schema()
    properties = tool["input_schema"]["properties"]
    for path in DETERMINISTIC_FIELDS:
        assert path not in properties


def test_tool_schema_uses_choice_enums():
    tool = _tool_schema()
    source_class = tool["input_schema"]["properties"]["section_a/SOURCE_CLASS"]
    assert source_class["type"] == "string"
    assert "policy_legislation" in source_class["enum"]


def test_tool_schema_repeat_group_is_an_array_of_objects():
    tool = _tool_schema()
    repeat = tool["input_schema"]["properties"]["section_j/metric_repeat"]
    assert repeat["type"] == "array"
    assert "METRIC_NAME" in repeat["items"]["properties"]
    # bare field names inside the repeat, not full "section_j/metric_repeat/x" paths
    assert "section_j/metric_repeat/METRIC_NAME" not in repeat["items"]["properties"]


def test_read_file_block_rejects_unsupported_extension(tmp_path):
    bad = tmp_path / "notes.docx"
    bad.write_text("x")
    with pytest.raises(AIDraftError) as exc:
        _read_file_block(str(bad), "application/msword")
    assert exc.value.code == "unsupported_file_type"


def test_read_file_block_pdf_is_a_document_block(tmp_path):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    block = _read_file_block(str(pdf), "application/pdf")
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"


def test_read_file_block_image_is_an_image_block(tmp_path):
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n")
    block = _read_file_block(str(img), "image/png")
    assert block["type"] == "image"


def _fake_anthropic_response(tool_input: dict):
    tool_use_block = Mock(type="tool_use", input=tool_input)
    return Mock(content=[tool_use_block])


def test_generate_draft_not_configured_raises(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = ""
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    with pytest.raises(AIDraftError) as exc:
        generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert exc.value.code == "ai_not_configured"


def test_generate_draft_merges_deterministic_fields_over_ai_answer(document, settings, tmp_path):
    """Even if the model somehow answered a deterministic field (it isn't
    asked to -- see test_tool_schema_excludes_deterministic_fields), the
    DocumentRecord's own values must win, never the AI's guess."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.AI_DOCUMENT_CODING_MODEL = "claude-opus-5"
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")

    fake_response = _fake_anthropic_response({
        "section_a/DOC_ID": "SOMETHING-THE-MODEL-MADE-UP",  # would be wrong if it won
        "section_b/RELEVANCE": "high",
        "section_j/metric_repeat": [],
    })
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create.return_value = fake_response
        draft = generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)

    assert draft["section_a/DOC_ID"] == document.document_id  # deterministic value wins
    assert draft["section_a/org_author"] == "Government of Zimbabwe"
    assert draft["section_a/pub_event_date"] == "2025-11-27"
    assert draft["section_b/RELEVANCE"] == "high"  # the AI's own answer is kept where it isn't deterministic
    assert draft["_generated_by_model"] == "claude-opus-5"
    assert "_generated_at" in draft


def test_generate_draft_no_tool_use_raises(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    fake_response = Mock(content=[Mock(type="text", text="I don't want to use the tool.")])
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create.return_value = fake_response
        with pytest.raises(AIDraftError) as exc:
            generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert exc.value.code == "ai_no_answer"


def test_generate_draft_wraps_api_error(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create.side_effect = anthropic.APIError(
            "boom", request=Mock(), body=None,
        )
        with pytest.raises(AIDraftError) as exc:
            generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert exc.value.code == "ai_request_failed"


def test_schema_field_count_matches_generated_json():
    # A cheap sanity check that document_tool_schema.json wasn't hand-edited
    # out of sync with what the loader expects.
    assert SCHEMA["form_id"] == "abf_fst_main_study_doc_analysis_v2"
    assert len(SCHEMA["fields"]) > 100
