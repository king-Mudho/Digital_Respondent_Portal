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

META = "https://api.meta.ai"


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
    assert kwargs["auth_token"] == "meta-key" and kwargs["base_url"] == META
    assert "api_key" not in kwargs  # the Anthropic key is never offered to Meta
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
    assert kwargs["base_url"] == META and kwargs["auth_token"] == "meta-key" and "api_key" not in kwargs
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


def test_the_real_sdk_sends_only_a_bearer_token_to_meta_even_with_an_anthropic_key_in_the_environment(settings, monkeypatch):
    # No mock: this is the installed SDK deciding which headers and URL it would use. A mocked client hid
    # exactly this (x-api-key instead of Bearer, and a doubled /v1) until a live 401 showed it.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-never-reach-meta")
    _configure(settings, base_url="https://api.meta.ai/v1", own_key="meta-key")  # an older setting with /v1
    client = coding_client(timeout=5.0)
    assert client.auth_headers == {"Authorization": "Bearer meta-key"}
    assert str(client._prepare_url("/v1/messages")) == "https://api.meta.ai/v1/messages"


def test_the_real_sdk_still_uses_the_anthropic_key_header_for_anthropic(settings):
    _configure(settings, anthropic_key="sk-ant-test")
    client = coding_client(timeout=5.0)
    assert client.auth_headers == {"X-Api-Key": "sk-ant-test"}
    assert str(client._prepare_url("/v1/messages")) == "https://api.anthropic.com/v1/messages"


def _bad_request(message):
    import anthropic

    return anthropic.BadRequestError(message, response=Mock(status_code=400, headers={}, request=Mock()), body=None)


def _final(response):
    cm = Mock()
    cm.__enter__ = Mock(return_value=Mock(get_final_message=Mock(return_value=response)))
    cm.__exit__ = Mock(return_value=False)
    return cm


ANSWER = Mock(content=[Mock(type="tool_use", input={"section_b__RELEVANCE": "high", "section_j__metric_repeat": []})], stop_reason="tool_use")


def test_meta_is_asked_for_any_tool_because_it_refuses_a_named_one_and_anthropic_keeps_the_named_one(document, settings, tmp_path):
    pdf = tmp_path / "s.pdf"
    _blank_pdf(pdf)
    for base_url, own_key, expected in ((META, "meta-key", {"type": "any"}),
                                        ("", "", {"type": "tool", "name": "submit_document_coding"})):
        _configure(settings, base_url=base_url, own_key=own_key)
        with patch("anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.stream.return_value = _final(ANSWER)
            generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
        assert client_cls.return_value.messages.stream.call_args.kwargs["tool_choice"] == expected


def test_if_meta_refuses_any_too_the_request_is_sent_again_without_tool_choice(document, settings, tmp_path):
    _configure(settings, base_url=META, own_key="meta-key")
    pdf = tmp_path / "s.pdf"
    _blank_pdf(pdf)
    with patch("anthropic.Anthropic") as client_cls:
        client_cls.return_value.messages.stream.side_effect = [_bad_request("`tool_choice` any is not supported"), _final(ANSWER)]
        draft = generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
    calls = client_cls.return_value.messages.stream.call_args_list
    assert calls[0].kwargs["tool_choice"] == {"type": "any"} and "tool_choice" not in calls[1].kwargs
    assert draft["section_b/RELEVANCE"] == "high"


def test_other_refusals_are_not_retried(document, settings, tmp_path):
    pdf = tmp_path / "s.pdf"
    _blank_pdf(pdf)
    for base_url, own_key, message in ((META, "meta-key", "the PDF is too large"), ("", "", "tool_choice is wrong")):
        _configure(settings, base_url=base_url, own_key=own_key)
        with patch("anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.stream.side_effect = [_bad_request(message), _final(ANSWER)]
            with pytest.raises(AIDraftError) as exc:
                generate_draft(document, source_path=str(pdf), source_content_type="application/pdf", user=None)
        assert exc.value.code == "ai_request_failed" and client_cls.return_value.messages.stream.call_count == 1


def test_the_details_call_also_falls_back_when_meta_refuses_any(settings, tmp_path):
    _configure(settings, base_url=META, own_key="meta-key")
    pdf = tmp_path / "s.pdf"
    _blank_pdf(pdf)
    response = Mock(content=[Mock(type="tool_use", input={"title": "A Report", "document_type": "OFFICIAL"})])
    with patch("anthropic.Anthropic") as client_cls:
        client_cls.return_value.messages.create.side_effect = [_bad_request("tool_choice not supported"), response]
        details = extract_document_details(str(pdf), "application/pdf")
    assert details["title"] == "A Report" and "tool_choice" not in client_cls.return_value.messages.create.call_args.kwargs
