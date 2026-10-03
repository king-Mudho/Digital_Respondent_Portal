"""The PROIT model comparison is only worth running if its measurements are right: a mixed-up A/B key, a wrong cost
or a quote check that always passes would produce a confident, wrong answer about which AI to trust."""

import json
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError

from apps.proit.management.commands import compare_proit_models as cmp

MODULE = "apps.proit.management.commands.compare_proit_models"
FIELDS = {"legal_name": ("Legal name", "org", "x"), "year_established": ("Year established", "org", "x")}


def _finding(field_id, value="Founded 1969", url="https://a.example/x", quote="founded in 1969", status="found"):
    return {"field_id": field_id, "status": status, "value": value, "confidence": "HIGH",
            "sources": [{"title": "T", "url": url, "quote": quote, "authority": "TIER_3_MEDIA"}]}


def _response(rid, output, inp=1000, out=50, cached=0):
    return {"id": rid, "output": output, "usage": {"input_tokens": inp, "output_tokens": out, "input_tokens_details": {"cached_tokens": cached}}}


def _call(findings, call_id="c1"):
    return {"type": "function_call", "name": "record_findings", "call_id": call_id,
            "arguments": json.dumps({"summary": "s", "findings": findings})}


def _search(url="https://a.example/x"):
    return {"type": "web_search_call", "results": [{"type": "text_result", "url": url, "title": "T", "snippet": "s"}]}


class FakePost:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "body": json, "headers": headers})
        item = self.responses.pop(0)
        return Mock(status_code=200, json=lambda: item) if isinstance(item, dict) else item


def test_cost_uses_each_providers_published_prices():
    usage = {"in": 1_000_000, "out": 1_000_000, "searches": 1000, "cache_read": 0, "cache_write": 0}
    assert cmp.cost_usd("claude-sonnet-5", usage) == 22.0   # 2 + 10 + 10 for 1,000 searches
    assert cmp.cost_usd("muse-spark-1.3", usage) == 8.0     # 1.25 + 4.25 + 2.50
    assert cmp.cost_usd("some-unlisted-model", usage) is None


def test_banned_financing_wording_is_counted_in_values_and_notes():
    proposals = [{"value": "Loan approval history is public", "notes": ""}, {"value": "Fine", "notes": "a credit rating exists"}]
    assert cmp.banned_wording_count(proposals) == 2
    assert cmp.banned_wording_count([{"value": "Founded 1969", "notes": ""}]) == 0


def test_urls_are_read_from_raw_results_in_either_shape_and_from_citations():
    output = [
        _search("https://a.example/x"),
        {"type": "web_search_call", "action": {"results": [{"url": "https://c.example/z"}]}},
        {"type": "message", "content": [{"type": "output_text", "annotations": [{"type": "url_citation", "url": "https://b.example/y"}]}]},
    ]
    assert cmp.muse_urls(output) == {"https://a.example/x", "https://c.example/z", "https://b.example/y"}
    assert cmp.muse_search_count(output) == 2


def test_a_function_call_is_read_whether_its_arguments_are_json_text_or_an_object():
    assert cmp.muse_function_call([_call([])])[1]["summary"] == "s"
    obj = {"type": "function_call", "name": "record_findings", "call_id": "c", "arguments": {"summary": "obj", "findings": []}}
    assert cmp.muse_function_call([obj])[1]["summary"] == "obj"
    assert cmp.muse_function_call([{"type": "message"}]) is None


def test_muse_is_asked_to_finish_when_it_searches_without_recording_and_usage_is_summed():
    post = FakePost(
        _response("r1", [_search(), {"type": "message", "content": []}], inp=1000, out=50, cached=200),
        _response("r2", [_call([_finding("legal_name"), _finding("year_established")])], inp=1500, out=300),
    )
    raw, seen, usage, log = cmp.call_muse({"organisation": {"name": "X"}}, FIELDS, "muse-spark-1.3", "the-key", post=post)
    assert len(raw["findings"]) == 2 and seen == {"https://a.example/x"} and len(log) == 2
    assert post.calls[0]["headers"] == {"Authorization": "Bearer the-key"}
    assert post.calls[1]["body"]["previous_response_id"] == "r1" and "record_findings" in post.calls[1]["body"]["input"]
    assert usage == {"in": 2300, "out": 350, "searches": 1, "cache_read": 200, "cache_write": 0}


def test_an_incomplete_answer_is_sent_back_with_the_function_output_for_that_call():
    fields = {f"f{i}": (f"F{i}", "m", "r") for i in range(4)}
    post = FakePost(
        _response("r1", [_call([_finding("f0")], call_id="call-9")]),
        _response("r2", [_call([_finding("f0"), _finding("f1"), _finding("f2")])]),
    )
    raw, *_ = cmp.call_muse({"organisation": {"name": "X"}}, fields, "muse-spark-1.3", "k", post=post)
    assert len(raw["findings"]) == 3
    second = post.calls[1]["body"]["input"][0]
    assert second["type"] == "function_call_output" and second["call_id"] == "call-9" and "Incomplete" in second["output"]


def test_a_refused_request_raises_with_the_status_and_never_the_key():
    from apps.proit.muse import MuseError

    post = FakePost(Mock(status_code=401, text="invalid credentials"))
    with pytest.raises(MuseError) as exc:
        cmp.call_muse({"organisation": {"name": "X"}}, FIELDS, "muse-spark-1.3", "secret-key-123", post=post)
    assert "401" in str(exc.value) and "secret-key-123" not in str(exc.value)


def test_a_quote_is_found_only_when_it_is_really_on_the_page():
    page = "<html><script>var x='was founded in 1969'</script><p>The company  was\nfounded in 1969 in Harare.</p></html>"
    assert cmp.quote_status("https://a.example", "was founded in 1969", fetch=lambda u: page) == "quote_found"
    assert cmp.quote_status("https://a.example", "was founded in 1985", fetch=lambda u: page) == "quote_not_found"
    assert cmp.quote_status("https://a.example", "", fetch=lambda u: page) == "quote_not_found"
    assert cmp.quote_status("https://a.example", "x", fetch=lambda u: None) == "unchecked_format"

    def dead(_url):
        raise OSError("connection refused")
    assert cmp.quote_status("https://a.example", "x", fetch=dead) == "unreachable"


def test_a_quote_that_appears_only_inside_a_script_is_not_counted():
    page = "<script>var x='was founded in 1969'</script><p>Nothing here</p>"
    assert cmp.quote_status("https://a.example", "was founded in 1969", fetch=lambda u: page) == "quote_not_found"


def test_organisations_in_the_study_sample_are_refused_and_a_missing_database_is_reported():
    with pytest.raises(CommandError, match="Seed Co"):
        cmp.refuse_sample_organisations(["Seed Co Limited", "Cottco Holdings"], in_sample=lambda n: n.startswith("Seed"))
    assert cmp.refuse_sample_organisations(["Cottco Holdings"], in_sample=lambda n: False) is True

    def no_db(_n):
        raise OperationalError("no database")
    assert cmp.refuse_sample_organisations(["Cottco Holdings"], in_sample=no_db) is False


def test_research_one_records_cost_and_clean_findings_and_survives_a_failure(monkeypatch):
    raw = {"summary": "s", "findings": [_finding("legal_name"), _finding("year_established", url="https://not-returned.example/q")]}
    usage = {"in": 1_000_000, "out": 0, "searches": 0, "cache_read": 0, "cache_write": 0}
    with patch(f"{MODULE}.call_muse", return_value=(raw, {"https://a.example/x"}, usage, [])):
        done = cmp.research_one("muse", "Cottco", pr_fields(), model="muse-spark-1.3", key="k", check_quotes=False)
    by_field = {p["field_id"]: p for p in done["proposals"]}
    assert done["error"] is None and done["cost_usd"] == 1.25
    assert by_field["legal_name"]["status"] == "found"
    assert by_field["year_established"]["status"] == "not_found"  # a URL the search never returned is dropped
    assert any("not returned" in d["reason"] for d in done["dropped"])
    with patch(f"{MODULE}.call_muse", side_effect=RuntimeError("boom")):
        failed = cmp.research_one("muse", "Cottco", pr_fields(), model="muse-spark-1.3", key="k", check_quotes=False)
    assert "boom" in failed["error"] and failed["proposals"] == []


def pr_fields():
    from apps.proit import ai_research as pr
    return {k: v for k, v in pr.ai_fields().items() if k in FIELDS}


def _result(arm, org, fields, value="v"):
    proposals = [{"field_id": f, "status": "found", "value": value, "confidence": "HIGH", "notes": "",
                  "sources": [{"url": "https://a.example", "quote": "q", "quote_check": "quote_found"}]} for f in fields]
    usage = {"in": 1_000_000, "out": 0, "searches": 0, "cache_read": 0, "cache_write": 0}
    model = "claude-sonnet-5" if arm == "claude" else "muse-spark-1.3"
    return {"organisation": org, "arm": arm, "model": model, "seconds": 1.0, "usage": usage, "cost_usd": cmp.cost_usd(model, usage),
            "proposals": proposals, "dropped": [], "banned_wording": 0, "error": None}


def test_blind_review_shuffles_a_and_b_and_the_key_recovers_who_wrote_what():
    fields = {f"f{i}": (f"F{i}", "m", "r") for i in range(30)}
    claude, muse = [_result("claude", "Org", fields, "from claude")], [_result("muse", "Org", fields, "from muse")]
    rows, key = cmp.build_review(claude, muse, fields, seed=7)
    assert len(rows) == len(key) == 30
    assert {k["A"] for k in key.values()} == {"claude", "muse"}  # not always the same arm in position A
    for row in rows:
        mapping = key[f"{row['organisation']}|{row['field_id']}"]
        assert row["A_value"] == f"from {mapping['A']}" and row["B_value"] == f"from {mapping['B']}"


def test_scoring_unblinds_through_the_key_so_each_verdict_lands_on_the_right_model():
    fields = {f"f{i}": (f"F{i}", "m", "r") for i in range(20)}
    claude, muse = [_result("claude", "Org", fields)], [_result("muse", "Org", fields)]
    rows, key = cmp.build_review(claude, muse, fields, seed=3)
    for row in rows:  # the reviewer, who cannot see the key, marks Claude's answers C and Muse's X
        mapping = key[f"{row['organisation']}|{row['field_id']}"]
        row["A_verdict"] = "C" if mapping["A"] == "claude" else "X"
        row["B_verdict"] = "C" if mapping["B"] == "claude" else "X"
    summary = cmp.score(rows, key, claude, muse, total_fields=20)
    assert summary["claude"]["precision"] == 1.0 and summary["muse"]["precision"] == 0.0
    assert summary["muse"]["fabricated"] == 20 and summary["claude"]["fabricated"] == 0
    failed = {label for label, ok, _ in cmp.thresholds(summary) if not ok}
    assert "Accuracy no more than 5 points below the current model" in failed


def test_scoring_refuses_a_row_left_unmarked_and_passes_when_muse_matches_and_is_cheaper():
    fields = {"f0": ("F0", "m", "r")}
    claude, muse = [_result("claude", "Org", fields)], [_result("muse", "Org", fields)]
    rows, key = cmp.build_review(claude, muse, fields, seed=1)
    with pytest.raises(CommandError, match="needs a verdict"):
        cmp.score(rows, key, claude, muse, total_fields=1)
    for row in rows:
        row["A_verdict"] = row["B_verdict"] = "C"
    summary = cmp.score(rows, key, claude, muse, total_fields=1)
    assert all(ok for _label, ok, _detail in cmp.thresholds(summary))  # same accuracy, 37.5% cheaper at 1M input tokens


def test_reviewing_muse_alone_puts_it_in_a_with_nothing_in_b_and_needs_no_b_verdict():
    fields = {f"f{i}": (f"F{i}", "m", "r") for i in range(5)}
    muse = [_result("muse", "Org", fields)]
    rows, key = cmp.build_review([], muse, fields, seed=1)
    assert len(rows) == 5 and all(k == {"A": "muse", "B": None} for k in key.values())
    assert all(r["B_status"] == "n/a" and r["A_status"] == "found" for r in rows)
    for row in rows:
        row["A_verdict"] = "C"  # B stays empty and must not be demanded
    summary = cmp.score(rows, key, [], muse, total_fields=5)
    assert summary["claude"] is None and summary["muse"]["precision"] == 1.0 and summary["muse"]["judged"] == 5


def test_muse_alone_is_judged_on_absolute_checks_that_can_fail_and_the_rest_is_information_only():
    fields = {"f0": ("F0", "m", "r")}
    muse = [_result("muse", "Org", fields)]
    rows, key = cmp.build_review([], muse, fields, seed=1)
    rows[0]["A_verdict"] = "C"
    good = cmp.thresholds(cmp.score(rows, key, [], muse, total_fields=1))
    assert [ok for _l, ok, _d in good] == [True, True, True, None]  # the last cannot be judged without Claude
    assert "need a Claude run" in good[-1][0]

    muse[0]["banned_wording"], muse[0]["error"] = 2, "boom"
    bad = {label: ok for label, ok, _d in cmp.thresholds(cmp.score(rows, key, [], muse, total_fields=1))}
    assert bad["No banned financing wording"] is False and bad["No organisation failed"] is False

    muse[0]["banned_wording"], muse[0]["error"] = 0, None
    muse[0]["proposals"][0]["sources"][0]["quote_check"] = "quote_not_found"
    poor = {label: ok for label, ok, _d in cmp.thresholds(cmp.score(rows, key, [], muse, total_fields=1))}
    assert poor["At least 95% of cited quotes found on the page"] is False


def test_a_muse_run_refuses_to_start_without_the_key_in_the_environment(db, monkeypatch, tmp_path):
    monkeypatch.delenv("META_API_KEY", raising=False)
    with pytest.raises(CommandError, match="META_API_KEY"):
        call_command("compare_proit_models", "run", "--arm", "muse", "--out", str(tmp_path / "m.json"), "--orgs", "Cottco Holdings Limited")
