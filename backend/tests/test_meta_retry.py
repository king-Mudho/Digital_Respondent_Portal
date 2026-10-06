"""Meta busy or failing for a moment (apps/proit/muse.py post_responses, 2026-10-06). Under test: a busy answer (429)
or a server error (5xx) is retried after the configured waits and the search carries on; a refusal about the request
or the account (400, 402, 403) fails at once; a connection failure is retried; once the retries run out the error is
the one the search already reported."""

from unittest.mock import Mock

import pytest
import requests

from apps.proit import muse


def _response(status, payload=None, text=""):
    return Mock(status_code=status, json=Mock(return_value=payload or {}), text=text or str(payload))


def _poster(*answers):
    """A fake requests.post that gives each answer in turn (an exception class is raised)."""
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs)
        answer = answers[len(calls) - 1]
        if isinstance(answer, type) and issubclass(answer, Exception):
            raise answer("down")
        return answer

    post.calls = calls
    return post


@pytest.mark.parametrize("status", [429, 500, 502, 503, 529])
def test_a_busy_or_failing_meta_is_asked_again_after_waiting(status, settings):
    settings.AI_TRANSIENT_RETRY_DELAYS = [30, 90, 180]
    waits = []
    post = _poster(_response(status, text="busy"), _response(status, text="busy"), _response(200, {"output": ["ok"]}))
    assert muse.post_responses("k", {"input": "x"}, post, sleep=waits.append) == {"output": ["ok"]}
    assert waits == [30, 90] and len(post.calls) == 3


@pytest.mark.parametrize("status", [400, 401, 402, 403])
def test_a_refusal_about_the_request_or_account_fails_at_once(status, settings):
    settings.AI_TRANSIENT_RETRY_DELAYS = [30, 90, 180]
    waits = []
    post = _poster(_response(status, text="no credit"))
    with pytest.raises(muse.MuseError, match=f"Meta API returned {status}"):
        muse.post_responses("k", {}, post, sleep=waits.append)
    assert waits == [] and len(post.calls) == 1


def test_after_the_last_retry_the_search_fails_as_before(settings):
    settings.AI_TRANSIENT_RETRY_DELAYS = [30, 90, 180]
    waits = []
    post = _poster(*[_response(429, text="rate limit")] * 4)
    with pytest.raises(muse.MuseError, match="Meta API returned 429"):
        muse.post_responses("k", {}, post, sleep=waits.append)
    assert waits == [30, 90, 180] and len(post.calls) == 4


def test_a_connection_failure_is_retried_but_a_read_timeout_is_not(settings):
    settings.AI_TRANSIENT_RETRY_DELAYS = [5]
    waits = []
    post = _poster(requests.ConnectionError, _response(200, {"output": []}))
    assert muse.post_responses("k", {}, post, sleep=waits.append) == {"output": []}
    assert waits == [5]

    # Meta may already have done (and billed) the work behind a read timeout.
    post = _poster(requests.ReadTimeout)
    with pytest.raises(requests.ReadTimeout):
        muse.post_responses("k", {}, post, sleep=waits.append)
    assert waits == [5]


def test_retries_can_be_turned_off(settings):
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    post = _poster(_response(503, text="down"))
    with pytest.raises(muse.MuseError):
        muse.post_responses("k", {}, post, sleep=lambda s: pytest.fail("waited"))


def test_a_search_conversation_survives_a_busy_spell_mid_way(settings, monkeypatch):
    # The turns already made are kept: the conversation resumes, it does not start again.
    settings.AI_TRANSIENT_RETRY_DELAYS = [1]
    monkeypatch.setattr(muse.time, "sleep", lambda s: None)
    first = {"output": [{"type": "web_search_call", "results": [{"url": "https://example.co.zw/contact"}]}],
             "usage": {"input_tokens": 10, "output_tokens": 5}, "id": "r1"}
    final = {"output": [{"type": "function_call", "name": "record", "call_id": "c1",
                         "arguments": '{"contacts": [], "summary": "nothing published"}'}],
             "usage": {"input_tokens": 10, "output_tokens": 5}, "id": "r2"}
    post = _poster(_response(200, first), _response(429, text="busy"), _response(200, final))
    raw, seen, usage, _log = muse.search_conversation(
        system="s", prompt="p", tool={"name": "record", "description": "d", "input_schema": {"type": "object"}},
        items_key="contacts", min_items=0, incomplete="{got}", nudge="n", model="m", key="k", post=post,
    )
    assert raw["summary"] == "nothing published" and "https://example.co.zw/contact" in seen
    assert len(post.calls) == 3
    # The retried request is the same second turn, continuing from the first response.
    assert post.calls[1]["json"] == post.calls[2]["json"] and post.calls[2]["json"]["previous_response_id"] == "r1"

