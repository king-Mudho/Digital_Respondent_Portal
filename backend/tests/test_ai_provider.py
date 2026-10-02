"""Switching document coding to another provider is configuration, and these are the rules around it:
documents and keys only ever go to an allowlisted https host, the Anthropic key never leaves for another
provider, and the record says which company received the document."""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from pypdf import PdfWriter

from apps.evidence.ai_coding import (
    AIDraftError,
    ai_coding_is_configured,
    coding_api_key,
    coding_client,
    coding_provider,
    extract_document_details,
    generate_draft,
)
from apps.evidence.models import DocumentRecord
from apps.evidence.services import generate_document_id

META = "https://api.meta.ai/v1"


@pytest.fixture
def document(db):
    return DocumentRecord.objects.create(
        document_id=generate_document_id(), title="Provider test document", author_or_speaker="Government of Zimbabwe",
        publication_or_event_date=date(2025, 11, 27), source_url_or_reference="https://example.com/x.pdf",
        document_type="OFFICIAL",
    )


def _blank_pdf(path, pages=2):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as handle:
        writer.write(handle)


def _configure(settings, *, base_url="", own_key="", anthropic_key="sk-ant-test"):
    settings.ANTHROPIC_API_KEY = anthropic_key
    settings.AI_DOCUMENT_CODING_BASE_URL = base_url
    settings.AI_DOCUMENT_CODING_API_KEY = own_key


def test_by_default_documents_go_to_anthropic_with_the_anthropic_key(settings):
    _configure(settings, own_key="would-be-ignored")
    with patch("anthropic.Anthropic") as client_cls:
        coding_client(timeout=5.0)
    kwargs = client_cls.call_args.kwargs
    assert kwargs["api_key"] == "sk-ant-test" and "base_url" not in kwargs
    assert coding_provider() == "api.anthropic.com"


def test_another_provider_gets_only_its_own_key_never_the_anthropic_key(settings):
    _configure(settings, base_url=META, own_key="meta-key")
    with patch("anthropic.Anthropic") as client_cls:
        coding_client(timeout=5.0)
    kwargs = client_cls.call_args.kwargs
    assert kwargs["api_key"] == "meta-key" and kwargs["base_url"] == META
    assert coding_provider() == "api.meta.ai"


def test_another_provider_with_no_key_of_its_own_is_off_and_does_not_borrow_the_anthropic_key(settings):
    _configure(settings, base_url=META, own_key="", anthropic_key="sk-ant-test")
    assert coding_api_key() == ""
    assert ai_coding_is_configured() is False


@pytest.mark.parametrize("url", [
    "http://api.meta.ai/v1",                    # not https
    "https://evil.example.com/v1",              # not on the list
    "https://api.meta.ai.evil.example/v1",      # list name used as a prefix
    "https://api.meta.ai@evil.example/v1",      # list name used as a username
    "ftp://api.meta.ai/v1",
])
def test_an_endpoint_off_the_allowlist_is_refused_before_anything_is_sent(settings, url):
    _configure(settings, base_url=url, own_key="meta-key")
    with patch("anthropic.Anthropic") as client_cls:
        with pytest.raises(AIDraftError) as exc:
            coding_client(timeout=5.0)
    assert exc.value.code == "ai_provider_not_allowed"
    client_cls.assert_not_called()


def test_a_full_draft_goes_to_the_configured_provider_and_names_it(document, settings, tmp_path):
    _configure(settings, base_url=META, own_key="meta-key")
    settings.AI_DOCUMENT_CODING_MODEL = "muse-spark-1.3"
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf)
    response = Mock(content=[Mock(type="tool_use", input={"section_b__RELEVANCE": "high", "section_j__metric_repeat": []})])
    with patch("anthropic.Anthropic") as client_cls:
        client_cls.return_value.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = response
        draft = generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    kwargs = client_cls.call_args.kwargs
    assert kwargs["base_url"] == META and kwargs["api_key"] == "meta-key"
    assert draft["_generated_by_provider"] == "api.meta.ai" and draft["_generated_by_model"] == "muse-spark-1.3"


def test_reading_a_documents_details_goes_to_the_same_provider(settings, tmp_path):
    _configure(settings, base_url=META, own_key="meta-key")
    pdf = tmp_path / "source.pdf"
    _blank_pdf(pdf)
    response = Mock(content=[Mock(type="tool_use", input={"title": "A Report", "document_type": "OFFICIAL"})])
    with patch("anthropic.Anthropic") as client_cls:
        client_cls.return_value.messages.create.return_value = response
        details = extract_document_details(str(pdf), "application/pdf")
    assert client_cls.call_args.kwargs["base_url"] == META
    assert details["title"] == "A Report"
