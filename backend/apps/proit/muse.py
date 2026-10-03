"""PROIT desk research on Meta's Muse Spark, through Meta's Responses API (the only Meta endpoint with web search).

Used by ai_research.run_research when AI_PROIT_PROVIDER is "meta", and by the compare_proit_models command. It
returns exactly what ai_research.call_model returns, so the same clean_findings rules apply to both providers.

What Meta's search cannot do that Anthropic's can, and how that is handled:
  * No blocked-domain list at request time. Personal and social pages are therefore dropped AFTER the search,
    by clean_findings (ai_research.BLOCKED_DOMAINS and PERSONAL_URL), not kept away from the model.
  * No cap on searches per request. The conversation is still capped by MAX_TURNS, and searches are counted.
The endpoint is fixed here, never configurable, so documents and the key can only go to Meta.
"""

import json

import requests

from . import ai_research as pr

META_RESPONSES_URL = "https://api.meta.ai/v1/responses"


class MuseError(Exception):
    pass


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def muse_urls(output: list) -> set[str]:
    """Every URL the search returned (raw results) or the answer cited (url_citation annotations).
    Read defensively: Meta's docs give no complete example of the output."""
    urls: set[str] = set()
    for item in output:
        if item.get("type") == "web_search_call":
            urls |= {n["url"] for n in _walk(item) if isinstance(n.get("url"), str)}
        for node in _walk(item.get("content")):
            if node.get("type") == "url_citation" and isinstance(node.get("url"), str):
                urls.add(node["url"])
    return urls


def muse_search_count(output: list) -> int:
    return sum(1 for item in output if item.get("type") == "web_search_call")


def muse_function_call(output: list, name: str = "record_findings"):
    for item in output:
        if item.get("type") == "function_call" and item.get("name") == name:
            args = item.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            return item.get("call_id"), dict(args or {})
    return None


def post_responses(key: str, body: dict, post=requests.post) -> dict:
    response = post(META_RESPONSES_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=600)
    if response.status_code >= 400:
        raise MuseError(f"Meta API returned {response.status_code}: {response.text[:500]}")
    return response.json()


def search_conversation(*, system: str, prompt: str, tool: dict, items_key: str, min_items: int, incomplete: str,
                        nudge: str, model: str, key: str, post=requests.post):
    """A web-search conversation on Muse that ends when the model calls `tool`. Shared by PROIT and the contact
    finder. Returns (tool input, urls returned, usage, raw responses)."""
    function = {"type": "function", "name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}
    body = {
        "model": model, "instructions": system, "input": prompt,
        "tools": [{"type": "web_search"}, function], "include": ["web_search_call.results"],
        "max_output_tokens": pr.MAX_OUTPUT_TOKENS,
    }
    seen: set[str] = set()
    usage = {"in": 0, "out": 0, "searches": 0, "cache_read": 0, "cache_write": 0}
    raw_log, reminders = [], 0
    for _turn in range(pr.MAX_TURNS + pr.MAX_REMINDERS):
        response = post_responses(key, body, post)
        raw_log.append(response)
        output = response.get("output") or []
        used = response.get("usage") or {}
        cached = (used.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0
        usage["in"] += max((used.get("input_tokens", 0) or 0) - cached, 0)
        usage["cache_read"] += cached
        usage["out"] += used.get("output_tokens", 0) or 0
        usage["searches"] += muse_search_count(output)
        seen |= muse_urls(output)
        call = muse_function_call(output, tool["name"])
        if call:
            call_id, answer = call
            answer[items_key] = pr._as_list(answer.get(items_key))
            if len(answer[items_key]) >= min_items or reminders >= pr.MAX_REMINDERS:
                return answer, seen, usage, raw_log
            reminders += 1
            next_input = [{"type": "function_call_output", "call_id": call_id,
                           "output": incomplete.format(got=len(answer[items_key]))}]
        else:
            next_input = nudge
        body = {**body, "previous_response_id": response.get("id"), "input": next_input}
    raise MuseError("Muse did not finish recording its findings.")


def call_muse(context: dict, fields: dict, model: str, key: str, post=requests.post):
    """PROIT's search conversation on Muse. Returns (tool input, urls returned, usage, raw responses)."""
    args = pr._proit_conversation_args(context, fields)
    return search_conversation(**args, model=model, key=key, post=post)
