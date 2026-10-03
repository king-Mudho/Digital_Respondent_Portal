"""The provider check must say FAIL when a provider answers wrongly, or the script that gates a switch on it is decoration."""

from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

COMMAND = "apps.evidence.management.commands.check_ai_provider.coding_client"


def _answer(value):
    return Mock(content=[Mock(type="tool_use", input={"value": value})], usage=Mock(input_tokens=10, output_tokens=5))


def _client(plain, streamed_first, streamed_pdf):
    client = MagicMock()
    client.messages.create.return_value = plain
    stream = client.messages.stream.return_value.__enter__.return_value
    stream.get_final_message.side_effect = [streamed_first, streamed_pdf]
    return client


def test_a_provider_that_answers_all_three_correctly_passes(settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    out = StringIO()
    with patch(COMMAND, return_value=_client(_answer(17), _answer(17), _answer(4821))):
        call_command("check_ai_provider", stdout=out)
    assert "All 3 checks passed" in out.getvalue() and "FAIL" not in out.getvalue()


def test_a_provider_that_misreads_the_pdf_fails_the_check(settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    out = StringIO()
    with patch(COMMAND, return_value=_client(_answer(17), _answer(17), _answer(999))):
        with pytest.raises(CommandError, match="1 of 3 checks failed"):
            call_command("check_ai_provider", stdout=out)
    assert "FAIL  PDF attachment" in out.getvalue()


def test_a_provider_that_errors_is_reported_not_crashed_and_never_shows_a_key(settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-secret-value"
    client = Mock()
    client.messages.create.side_effect = RuntimeError("unsupported field tool_choice")
    client.messages.stream.side_effect = RuntimeError("unsupported content type document")
    out = StringIO()
    with patch(COMMAND, return_value=client):
        with pytest.raises(CommandError, match="3 of 3 checks failed"):
            call_command("check_ai_provider", stdout=out)
    assert "unsupported field tool_choice" in out.getvalue()
    assert "sk-ant-secret-value" not in out.getvalue()


def _proit_meta(settings):
    settings.AI_PROIT_PROVIDER, settings.AI_PROIT_API_KEY, settings.AI_PROIT_RESEARCH_MODEL = "meta", "meta-key", "muse-spark-1.3"


def _year_answer(value, searched=True):
    output = [{"type": "function_call", "name": "report_number", "call_id": "c1", "arguments": f'{{"value": {value}}}'}]
    if searched:
        output.insert(0, {"type": "web_search_call", "results": [{"url": "https://en.wikipedia.org/wiki/Zimbabwe"}]})
    return {"id": "r1", "output": output, "usage": {"input_tokens": 300, "output_tokens": 20}}


def test_the_proit_check_passes_when_meta_searches_and_answers_correctly(settings):
    _proit_meta(settings)
    out = StringIO()
    with patch("apps.proit.muse.post_responses", return_value=_year_answer(1980)) as post:
        call_command("check_ai_provider", "--proit", stdout=out)
    assert "All 3 PROIT checks passed" in out.getvalue()
    body = post.call_args.args[1]
    assert {"type": "web_search"} in body["tools"] and post.call_args.args[0] == "meta-key"


def test_the_proit_check_fails_when_meta_answers_without_searching_or_wrongly(settings):
    _proit_meta(settings)
    with patch("apps.proit.muse.post_responses", return_value=_year_answer(1979, searched=False)):
        with pytest.raises(CommandError, match="2 of 3 PROIT checks failed"):
            call_command("check_ai_provider", "--proit", stdout=StringIO())


def test_the_proit_check_asks_again_when_meta_searches_but_does_not_answer_in_the_format(settings):
    _proit_meta(settings)
    first = {"id": "r1", "output": [{"type": "web_search_call", "results": [{"url": "https://a.example"}]}, {"type": "message"}], "usage": {}}
    with patch("apps.proit.muse.post_responses", side_effect=[first, _year_answer(1980, searched=False)]) as post:
        call_command("check_ai_provider", "--proit", stdout=StringIO())
    assert post.call_args_list[1].args[1]["previous_response_id"] == "r1"


def test_the_proit_check_refuses_when_proit_is_not_set_to_meta(settings):
    settings.AI_PROIT_PROVIDER = "anthropic"
    with pytest.raises(CommandError, match="set to Anthropic"):
        call_command("check_ai_provider", "--proit", stdout=StringIO())


def test_the_check_refuses_to_run_with_no_key(settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(CommandError, match="No API key"):
        call_command("check_ai_provider", stdout=StringIO())
