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
    _TOOL_KEY_PATTERN,
    DETERMINISTIC_FIELDS,
    MAX_PDF_PAGES,
    AIDraftError,
    _read_file_block,
    _to_tool_key,
    _tool_schema,
    ai_coding_is_configured,
    generate_draft,
    parse_page_range,
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
        assert _to_tool_key(path) not in properties


def test_tool_schema_uses_choice_enums():
    tool = _tool_schema()
    source_class = tool["input_schema"]["properties"]["section_a__SOURCE_CLASS"]
    assert source_class["type"] == "string"
    assert "policy_legislation" in source_class["enum"]


def test_tool_schema_repeat_group_is_an_array_of_objects():
    tool = _tool_schema()
    repeat = tool["input_schema"]["properties"]["section_j__metric_repeat"]
    assert repeat["type"] == "array"
    assert "METRIC_NAME" in repeat["items"]["properties"]
    # bare field names inside the repeat, not full "section_j/metric_repeat/x" paths
    assert "section_j/metric_repeat/METRIC_NAME" not in repeat["items"]["properties"]


def test_read_file_block_rejects_unsupported_extension(tmp_path):
    bad = tmp_path / "notes.mp3"
    bad.write_text("x")
    with pytest.raises(AIDraftError) as exc:
        _read_file_block(str(bad), "audio/mpeg")
    assert exc.value.code == "unsupported_file_type"


def test_read_file_block_pdf_is_a_document_block(tmp_path):
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
    block, _ = _read_file_block(str(pdf), "application/pdf")
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"


def test_read_file_block_image_is_an_image_block(tmp_path):
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n")
    block, _ = _read_file_block(str(img), "image/png")
    assert block["type"] == "image"


def _stub_stream(mock_client_cls, response):
    """The client streams (the output is too long to request in one go), so the
    fake has to be a context manager whose final message is the response."""
    stream = mock_client_cls.return_value.messages.stream.return_value
    stream.__enter__.return_value.get_final_message.return_value = response


def _fake_anthropic_response(tool_input: dict):
    tool_use_block = Mock(type="tool_use", input=tool_input)
    return Mock(content=[tool_use_block])


def test_generate_draft_not_configured_raises(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = ""
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
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
    _blank_pdf(pdf, 3)

    fake_response = _fake_anthropic_response({
        "section_a__DOC_ID": "SOMETHING-THE-MODEL-MADE-UP",  # would be wrong if it won
        "section_b__RELEVANCE": "high",
        "section_j__metric_repeat": [],
    })
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake_response)
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
    _blank_pdf(pdf, 3)
    fake_response = Mock(content=[Mock(type="text", text="I don't want to use the tool.")])
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake_response)
        with pytest.raises(AIDraftError) as exc:
            generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert exc.value.code == "ai_no_answer"


def test_generate_draft_wraps_api_error(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.stream.side_effect = anthropic.APIError(
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


def test_tool_schema_property_names_are_valid():
    """The first real call (2026-09-19) was rejected by Anthropic:
    'Property keys should match pattern ^[a-zA-Z0-9_.-]{1,64}$' -- the form
    paths contain '/'. A mocked call can't see that; this checks the rule the
    real API enforces, on every property, including inside the repeat group."""
    schema = _tool_schema()["input_schema"]
    props = schema["properties"]
    assert all(_TOOL_KEY_PATTERN.match(k) for k in props), [k for k in props if not _TOOL_KEY_PATTERN.match(k)]
    assert all(_TOOL_KEY_PATTERN.match(k) for k in props["section_j__metric_repeat"]["items"]["properties"])
    assert all(_TOOL_KEY_PATTERN.match(k) for k in schema["required"])


def test_generate_draft_maps_tool_keys_back_to_form_paths(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
    fake_response = Mock(stop_reason="tool_use", content=[Mock(type="tool_use", input={"section_d__D1_STRENGTH": "moderate"})])
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake_response)
        draft = generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert draft["section_d/D1_STRENGTH"] == "moderate"
    assert "section_d__D1_STRENGTH" not in draft


def test_generate_draft_refuses_a_cut_off_answer(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
    fake_response = Mock(stop_reason="max_tokens", content=[Mock(type="tool_use", input={})])
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake_response)
        with pytest.raises(AIDraftError) as exc:
            generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    assert exc.value.code == "ai_answer_cut_off"  # never saved as a draft with fields missing


def test_parse_page_range():
    assert parse_page_range("12-60", 648) == (12, 60)
    assert parse_page_range(" 7 ", 648) == (7, 7)
    for bad in ["", "abc", "0-5", "60-12", "1-649"]:
        with pytest.raises(AIDraftError):
            parse_page_range(bad, 648)
    with pytest.raises(AIDraftError) as exc:
        parse_page_range(f"1-{MAX_PDF_PAGES + 1}", 648)
    assert exc.value.code == "page_range_too_long"


def _blank_pdf(path, pages):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def test_long_pdf_needs_a_page_range(tmp_path):
    long_pdf = tmp_path / "long.pdf"
    _blank_pdf(long_pdf, MAX_PDF_PAGES + 20)
    with pytest.raises(AIDraftError) as exc:
        _read_file_block(str(long_pdf), "application/pdf")
    assert exc.value.code == "pdf_too_long"
    assert f"{MAX_PDF_PAGES + 20} pages" in str(exc.value)


def test_page_range_sends_only_those_pages_and_says_so(tmp_path):
    import base64
    import io

    from pypdf import PdfReader

    long_pdf = tmp_path / "long.pdf"
    _blank_pdf(long_pdf, 150)
    block, described = _read_file_block(str(long_pdf), "application/pdf", "31-40")
    sent = PdfReader(io.BytesIO(base64.b64decode(block["source"]["data"])))
    assert len(sent.pages) == 10
    assert "pages 31-40 of a 150-page document" in described  # so locators use original page numbers


def test_short_pdf_is_sent_whole_without_a_range(tmp_path):
    pdf = tmp_path / "short.pdf"
    _blank_pdf(pdf, 12)
    _, described = _read_file_block(str(pdf), "application/pdf")
    assert "12 pages" in described


def test_output_budget_is_large_enough_for_a_full_answer(document, settings, tmp_path):
    """16,000 output tokens cut the first real NDS2 draft off. The request must
    ask for a budget in line with the model's limit, and stream it."""
    from apps.evidence.ai_coding import MAX_OUTPUT_TOKENS

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf, 3)
    fake_response = Mock(stop_reason="tool_use", content=[Mock(type="tool_use", input={})])
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake_response)
        generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
        sent = mock_client_cls.return_value.messages.stream.call_args.kwargs
    assert MAX_OUTPUT_TOKENS >= 32000
    assert sent["max_tokens"] == MAX_OUTPUT_TOKENS


# --- Reading every kind of document ------------------------------------------

def _docx(path, paragraphs):
    import zipfile

    body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
        f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def test_word_document_is_sent_as_text_with_no_page_numbers(tmp_path):
    f = tmp_path / "report.docx"
    _docx(f, ["Section 4. Warehouse receipts", "Para 4.2 grain becomes a bankable asset."])
    block, described = _read_file_block(str(f), "application/vnd.openxmlformats")
    assert block["type"] == "text"
    assert "Para 4.2 grain becomes a bankable asset." in block["text"]
    assert "no page numbers" in described


def test_excel_workbook_is_sent_as_text_with_sheet_names(tmp_path):
    import openpyxl

    f = tmp_path / "data.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Loans"
    wb.active.append(["year", "value"])
    wb.active.append([2024, 84])
    wb.save(f)
    block, _ = _read_file_block(str(f), "application/vnd.ms-excel")
    assert "## Sheet: Loans" in block["text"]
    assert "2024\t84" in block["text"]


def test_plain_text_and_csv_are_read(tmp_path):
    for name in ("notes.txt", "table.csv"):
        f = tmp_path / name
        f.write_text("a,b\n1,2", encoding="utf-8")
        block, _ = _read_file_block(str(f), "text/plain")
        assert "a,b" in block["text"]


def test_broken_word_file_says_so_instead_of_crashing(tmp_path):
    f = tmp_path / "broken.docx"
    f.write_bytes(b"not a zip at all")
    with pytest.raises(AIDraftError) as exc:
        _read_file_block(str(f), "")
    assert exc.value.code == "unreadable_document"


def test_empty_document_is_refused(tmp_path):
    f = tmp_path / "empty.docx"
    _docx(f, [])
    with pytest.raises(AIDraftError) as exc:
        _read_file_block(str(f), "")
    assert exc.value.code == "empty_document"


def test_audio_and_old_word_files_get_a_clear_instruction(tmp_path):
    for name, expect in (("call.mp3", "transcript"), ("old.doc", ".docx"), ("old.xls", ".xlsx")):
        f = tmp_path / name
        f.write_bytes(b"x")
        with pytest.raises(AIDraftError) as exc:
            _read_file_block(str(f), "")
        assert exc.value.code == "unsupported_file_type"
        assert expect in str(exc.value)


def test_oversize_photo_is_shrunk_under_the_api_image_limit(tmp_path):
    """The API rejects any image over 5 MB; phone photos routinely exceed it."""
    import base64
    import os

    from PIL import Image

    from apps.evidence.ai_coding import MAX_IMAGE_BYTES

    f = tmp_path / "photo.png"
    Image.frombytes("RGB", (2400, 2400), os.urandom(2400 * 2400 * 3)).save(f, format="PNG")  # incompressible noise
    assert f.stat().st_size > MAX_IMAGE_BYTES
    block, _ = _read_file_block(str(f), "image/png")
    assert block["source"]["media_type"] == "image/jpeg"
    assert len(base64.b64decode(block["source"]["data"])) <= MAX_IMAGE_BYTES


def test_text_document_reaches_the_model_and_records_token_use(document, settings, tmp_path):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    f = tmp_path / "report.docx"
    _docx(f, ["Para 1. Contract farming expands."])
    fake = Mock(stop_reason="tool_use", content=[Mock(type="tool_use", input={})], usage=Mock(input_tokens=1234, output_tokens=5678))
    with patch("anthropic.Anthropic") as mock_client_cls:
        _stub_stream(mock_client_cls, fake)
        draft = generate_draft(document, source_path=str(f), source_content_type="", user=None)
        content = mock_client_cls.return_value.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert content[0]["type"] == "text" and "Contract farming expands" in content[0]["text"]
    assert draft["_tokens_in"] == 1234 and draft["_tokens_out"] == 5678
