"""Side-by-side test of PROIT desk research on two AI providers, using PUBLIC organisations only.

Nothing here touches the database or any study record. Three steps:

  run     one provider researches each organisation with PROIT's own prompt, fields and clean-up rules, and
          every quote it cites is checked against the live page:
              manage.py compare_proit_models run --arm claude --out claude.json
              META_API_KEY=... manage.py compare_proit_models run --arm muse --out muse.json
  review  both results become one CSV for two people to mark, with A/B labels shuffled so the reviewer
          cannot tell which model wrote which answer (the key is kept in a separate file):
              manage.py compare_proit_models review --claude claude.json --muse muse.json --out-dir review
  score   the marked CSV is unblinded and compared against the thresholds proposed to the supervisors:
              manage.py compare_proit_models score --review review/review.csv --key review/key.json \
                  --claude claude.json --muse muse.json

The Meta key is read from the META_API_KEY environment variable only, never from an argument or a file,
and is never printed. Run this only with organisations that are not in the study sample.
"""

import csv
import html
import json
import os
import random
import re
import time
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import Error as DatabaseError

from apps.proit import ai_research as pr

DEFAULT_ORGS = [
    "Cottco Holdings Limited", "Tanganda Tea Company Limited", "Ariston Holdings Limited",
    "Windmill Limited", "Dairibord Holdings Limited",
]  # public companies, checked absent from the sample on 2026-10-02
META_RESPONSES_URL = "https://api.meta.ai/v1/responses"
DEFAULT_MUSE_MODEL = "muse-spark-1.3"

# USD per million tokens, and per 1,000 searches. Anthropic: platform.claude.com pricing page; Meta: Model API
# pricing page, Standard tier (checked 2026-10-02). Meta publishes no cache-write price, so it is taken as the input
# price; a model that is not listed gets no cost figure rather than a guess.
PRICES = {
    "claude-sonnet-5": {"inp": 2.0, "out": 10.0, "cache_read": 0.20, "cache_write": 2.50, "search": 10.0},
    "claude-opus-5": {"inp": 5.0, "out": 25.0, "cache_read": 0.50, "cache_write": 6.25, "search": 10.0},
    "muse-spark-1.3": {"inp": 1.25, "out": 4.25, "cache_read": 0.15, "cache_write": 1.25, "search": 2.50},
}
BANNED_WORDING = re.compile(r"\b(approved|loan approval|credit rating|bankability score|guarantee[ds]?)\b", re.I)
INCOMPLETE = (
    "Incomplete: you returned {got} findings but there are {want} fields. Call record_findings again with an entry for "
    "EVERY field: the fact and its source where you found one, and not_found only where you searched and found nothing."
)


def cost_usd(model: str, usage: dict):
    price = PRICES.get(model)
    if price is None:
        return None
    tokens = (
        usage.get("in", 0) * price["inp"] + usage.get("out", 0) * price["out"]
        + usage.get("cache_read", 0) * price["cache_read"] + usage.get("cache_write", 0) * price["cache_write"]
    ) / 1_000_000
    return round(tokens + usage.get("searches", 0) * price["search"] / 1000, 4)


def banned_wording_count(proposals: list[dict]) -> int:
    return sum(len(BANNED_WORDING.findall(f"{p.get('value', '')} {p.get('notes', '')}")) for p in proposals)


# --- Reading Meta's Responses API output (shapes are read defensively: the docs give no full example) ----------------

def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def muse_urls(output: list) -> set[str]:
    """Every URL the search returned (raw results) or the answer cited (url_citation annotations)."""
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


def _muse_post(post, key: str, body: dict) -> dict:
    response = post(META_RESPONSES_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=600)
    if response.status_code >= 400:
        raise CommandError(f"Meta API returned {response.status_code}: {response.text[:500]}")
    return response.json()


def call_muse(context: dict, fields: dict, model: str, key: str, post=requests.post):
    """PROIT's search conversation on Meta's Responses API. Returns (tool input, urls returned, usage, raw responses)."""
    tool = pr._findings_tool(fields)
    function = {"type": "function", "name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}
    body = {
        "model": model, "instructions": pr.SYSTEM_PROMPT, "input": pr.build_prompt(context, fields),
        "tools": [{"type": "web_search"}, function], "include": ["web_search_call.results"],
        "max_output_tokens": pr.MAX_OUTPUT_TOKENS,
    }
    seen: set[str] = set()
    usage = {"in": 0, "out": 0, "searches": 0, "cache_read": 0, "cache_write": 0}
    raw_log, reminders = [], 0
    for _turn in range(pr.MAX_TURNS + pr.MAX_REMINDERS):
        response = _muse_post(post, key, body)
        raw_log.append(response)
        output = response.get("output") or []
        used = response.get("usage") or {}
        cached = (used.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0
        usage["in"] += max((used.get("input_tokens", 0) or 0) - cached, 0)
        usage["cache_read"] += cached
        usage["out"] += used.get("output_tokens", 0) or 0
        usage["searches"] += muse_search_count(output)
        seen |= muse_urls(output)
        call = muse_function_call(output)
        if call:
            call_id, answer = call
            answer["findings"] = pr._as_list(answer.get("findings"))
            if len(answer["findings"]) >= max(1, len(fields) // 2) or reminders >= pr.MAX_REMINDERS:
                return answer, seen, usage, raw_log
            reminders += 1
            next_input = [{"type": "function_call_output", "call_id": call_id,
                           "output": INCOMPLETE.format(got=len(answer["findings"]), want=len(fields))}]
        else:
            next_input = "Now call record_findings with an entry for every field."
        body = {**body, "previous_response_id": response.get("id"), "input": next_input}
    raise CommandError("Muse did not finish recording its findings.")


# --- Checking that a cited quote is really on the cited page ---------------------------------------------------------

def _normalise(text: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip().lower()


def _fetch(url: str):
    response = requests.get(url, timeout=15, headers={"User-Agent": "ABF-FST-research-check"})
    response.raise_for_status()
    if "text" not in response.headers.get("content-type", "") and "html" not in response.headers.get("content-type", ""):
        return None
    return response.text[:3_000_000]


def quote_status(url: str, quote: str, fetch=_fetch) -> str:
    """quote_found / quote_not_found / unreachable / unchecked_format (a PDF or image is not read here)."""
    try:
        page = fetch(url)
    except Exception:  # a dead link or a refusal is a result, not a crash
        return "unreachable"
    if page is None:
        return "unchecked_format"
    wanted = _normalise(quote)
    return "quote_found" if wanted and wanted in _normalise(page) else "quote_not_found"


# --- One organisation, one provider ----------------------------------------------------------------------------------

def research_one(arm: str, name: str, fields: dict, *, model: str, key: str = "", check_quotes: bool = True) -> dict:
    context = {"organisation": {"name": name}, "person": {}}
    started, error, proposals, dropped, usage, raw_log = time.monotonic(), None, [], [], {}, []
    try:
        if arm == "claude":
            raw, seen, usage = pr.call_model(context, fields)
        else:
            raw, seen, usage, raw_log = call_muse(context, fields, model, key)
        proposals, dropped = pr.clean_findings(raw, seen, fields)
        if check_quotes:
            for proposal in proposals:
                for source in proposal["sources"]:
                    source["quote_check"] = quote_status(source["url"], source["quote"])
    except Exception as exc:  # one failed organisation must not lose the others
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    return {
        "organisation": name, "arm": arm, "model": model, "seconds": round(time.monotonic() - started, 1), "usage": usage,
        "cost_usd": cost_usd(model, usage) if usage else None, "proposals": proposals, "dropped": dropped,
        "banned_wording": banned_wording_count(proposals), "error": error, "raw": raw_log,
    }


def refuse_sample_organisations(names: list[str], in_sample=None):
    """Never send a study participant's organisation: stop if any name is in the sample. Best effort without a database."""
    def default(name: str) -> bool:
        from apps.sampling.models import Organisation
        return Organisation.objects.filter(name__icontains=name.split()[0]).exists()

    check = in_sample or default
    try:
        hits = [n for n in names if check(n)]
    except DatabaseError:
        return False  # no database here (e.g. a laptop): the caller warns
    if hits:
        raise CommandError(f"These look like organisations in the study sample, so they are refused: {', '.join(hits)}")
    return True


# --- Blind review and scoring ----------------------------------------------------------------------------------------

def _proposal(result: dict, field_id: str):
    return next((p for p in (result or {}).get("proposals", []) if p["field_id"] == field_id), None)


def _describe(p) -> tuple[str, str, str]:
    if p is None:
        return "error", "", ""
    sources = "\n".join(f"{s['url']} [{s.get('quote_check', '?')}] \"{s['quote']}\"" for s in p["sources"])
    return p["status"], p["value"], sources


def build_review(claude: list[dict], muse: list[dict], fields: dict, seed: int = 1):
    """(rows, key). With both providers, A/B is shuffled per row and the key says which is which. With one
    provider only, its answers are always A and B is "n/a" (there is nothing to blind)."""
    rng, rows, key = random.Random(seed), [], {}
    by_org = {(r["arm"], r["organisation"]): r for r in [*claude, *muse]}
    arms = [arm for arm, results in (("claude", claude), ("muse", muse)) if results]
    for org in sorted({r["organisation"] for r in [*claude, *muse]}):
        for field_id, (label, _module, _route) in fields.items():
            found = {arm: _proposal(by_org.get((arm, org)), field_id) for arm in arms}
            if not any(p and p["status"] != "not_found" for p in found.values()):
                continue
            if len(arms) == 2:
                swap = rng.random() < 0.5
                a_arm, b_arm = ("muse", "claude") if swap else ("claude", "muse")
            else:
                a_arm, b_arm = arms[0], None
            key[f"{org}|{field_id}"] = {"A": a_arm, "B": b_arm}
            (a_status, a_value, a_src) = _describe(found[a_arm])
            (b_status, b_value, b_src) = _describe(found[b_arm]) if b_arm else ("n/a", "", "")
            rows.append({
                "organisation": org, "field_id": field_id, "field": label,
                "A_status": a_status, "A_value": a_value, "A_sources": a_src,
                "B_status": b_status, "B_value": b_value, "B_sources": b_src,
                "A_verdict": "", "B_verdict": "", "reviewer_notes": "",
            })
    return rows, key


REVIEW_README = """How to mark the review sheet (review.csv)

For each row, open the cited source for answer A and for answer B and decide, separately for each:
  C  correct, and the source really shows it
  U  unsupported: the source does not show it (or the page will not open)
  X  wrong: the source or another reliable source contradicts it
Leave the verdict empty when the status is not_found. Do not guess which answer came from which model:
the labels are shuffled on purpose. Two people should mark independently; resolve differences by discussion.
If answer B says n/a, only one provider was run: mark answer A and leave B empty.
"""


def score(rows: list[dict], key: dict, claude: list[dict], muse: list[dict], total_fields: int) -> dict:
    tally = {arm: {"C": 0, "U": 0, "X": 0} for arm in ("claude", "muse")}
    for row in rows:
        mapping = key[f"{row['organisation']}|{row['field_id']}"]
        for label in ("A", "B"):
            verdict = (row[f"{label}_verdict"] or "").strip().upper()
            if mapping[label] is None or row[f"{label}_status"] in ("not_found", "error", "n/a"):
                continue
            if verdict not in ("C", "U", "X"):
                raise CommandError(f"Row {row['organisation']} / {row['field_id']}: answer {label} needs a verdict C, U or X.")
            tally[mapping[label]][verdict] += 1
    summary = {}
    for arm, results in (("claude", claude), ("muse", muse)):
        if not results:
            summary[arm] = None  # that provider was not run
            continue
        t = tally[arm]
        judged = sum(t.values())
        sources = [s for r in results for p in r["proposals"] for s in p["sources"]]
        reachable = [s for s in sources if s.get("quote_check") in ("quote_found", "quote_not_found")]
        costs = [r["cost_usd"] for r in results if r["cost_usd"] is not None]
        summary[arm] = {
            **t, "judged": judged, "precision": round(t["C"] / judged, 3) if judged else None,
            "fabricated": t["U"] + t["X"],
            "coverage": round(sum(1 for r in results for p in r["proposals"] if p["status"] != "not_found")
                              / max(1, len(results) * total_fields), 3),
            "quote_valid_rate": round(sum(1 for s in reachable if s["quote_check"] == "quote_found") / len(reachable), 3) if reachable else None,
            "dropped_sources": sum(len(r["dropped"]) for r in results),
            "banned_wording": sum(r["banned_wording"] for r in results),
            "errors": sum(1 for r in results if r["error"]),
            "cost_usd": round(sum(costs), 4) if costs else None,
            "searches": sum(r["usage"].get("searches", 0) for r in results if r["usage"]),
            "seconds": round(sum(r["seconds"] for r in results), 1),
        }
    return summary


def thresholds(summary: dict) -> list[tuple[str, bool | None, str]]:
    """(label, passed, detail). passed is None for a figure that cannot be judged without the other provider."""
    c, m = summary["claude"], summary["muse"]
    if c is None:  # Muse alone: only the absolute checks mean anything
        return [
            ("At least 95% of cited quotes found on the page", m["quote_valid_rate"] is not None and m["quote_valid_rate"] >= 0.95,
             f"{m['quote_valid_rate']}"),
            ("No banned financing wording", m["banned_wording"] == 0, f"{m['banned_wording']}"),
            ("No organisation failed", m["errors"] == 0, f"{m['errors']} failed"),
            ("Accuracy, invented claims and cost need a Claude run to compare", None,
             f"muse precision {m['precision']}, fabricated {m['fabricated']}, coverage {m['coverage']}, cost ${m['cost_usd']}"),
        ]
    cost_ok = c["cost_usd"] is not None and m["cost_usd"] is not None and m["cost_usd"] <= 0.7 * c["cost_usd"]
    return [
        ("Accuracy no more than 5 points below the current model", m["precision"] is not None and c["precision"] is not None
         and m["precision"] >= c["precision"] - 0.05, f"muse {m['precision']} vs claude {c['precision']}"),
        ("Fabricated or unsupported claims no more than the current model", m["fabricated"] <= c["fabricated"],
         f"muse {m['fabricated']} vs claude {c['fabricated']}"),
        ("At least 95% of cited quotes found on the page", m["quote_valid_rate"] is not None and m["quote_valid_rate"] >= 0.95,
         f"muse {m['quote_valid_rate']} (claude {c['quote_valid_rate']})"),
        ("No banned financing wording", m["banned_wording"] == 0, f"muse {m['banned_wording']} (claude {c['banned_wording']})"),
        ("At least 30% cheaper, measured", cost_ok, f"muse ${m['cost_usd']} vs claude ${c['cost_usd']}"),
        ("Failures no worse than the current model", m["errors"] <= c["errors"], f"muse {m['errors']} vs claude {c['errors']}"),
    ]


class Command(BaseCommand):
    help = "Compare PROIT desk research on Claude and Muse Spark, using public organisations only (see the module docstring)."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        run = sub.add_parser("run")
        run.add_argument("--arm", choices=["claude", "muse"], required=True)
        run.add_argument("--out", required=True)
        run.add_argument("--orgs", nargs="*", help="Organisation names (default: the five public companies)")
        run.add_argument("--model", help="Model name (default: the portal's PROIT model, or muse-spark-1.3)")
        run.add_argument("--no-quote-check", action="store_true")
        review = sub.add_parser("review")
        review.add_argument("--claude", help="Claude results (optional: leave out to review Muse alone)")
        review.add_argument("--muse", required=True)
        review.add_argument("--out-dir", required=True)
        review.add_argument("--seed", type=int, default=1)
        scoring = sub.add_parser("score")
        scoring.add_argument("--review", required=True)
        scoring.add_argument("--key", required=True)
        scoring.add_argument("--claude", help="Claude results (optional: leave out to score Muse alone)")
        scoring.add_argument("--muse", required=True)

    def handle(self, *args, **options):
        getattr(self, f"_{options['action']}")(options)

    def _run(self, options):
        from django.conf import settings

        arm, names = options["arm"], options["orgs"] or DEFAULT_ORGS
        if not refuse_sample_organisations(names):
            self.stdout.write(self.style.WARNING("No database here, so the sample check was skipped. Use only organisations you have checked."))
        key = ""
        if arm == "muse":
            key = os.environ.get("META_API_KEY", "").strip()
            if not key:
                raise CommandError("Set META_API_KEY in the environment (not as an argument) before running the Muse arm.")
        elif not (settings.ANTHROPIC_API_KEY or "").strip():
            raise CommandError("No ANTHROPIC_API_KEY is configured here; run the Claude arm on the server.")
        model = options["model"] or (settings.AI_PROIT_RESEARCH_MODEL if arm == "claude" else DEFAULT_MUSE_MODEL)
        fields, results = pr.ai_fields(), []
        for name in names:
            self.stdout.write(f"{arm}: researching {name} ...")
            result = research_one(arm, name, fields, model=model, key=key, check_quotes=not options["no_quote_check"])
            found = sum(1 for p in result["proposals"] if p["status"] != "not_found")
            self.stdout.write(f"  {'FAILED: ' + result['error'] if result['error'] else f'{found} of {len(fields)} found'}"
                              f"  ({result['seconds']}s, cost ${result['cost_usd']})")
            results.append(result)
        Path(options["out"]).write_text(json.dumps(results, indent=2), encoding="utf-8")
        self.stdout.write(f"Wrote {options['out']}")

    def _review(self, options):
        claude = json.loads(Path(options["claude"]).read_text(encoding="utf-8")) if options["claude"] else []
        muse = json.loads(Path(options["muse"]).read_text(encoding="utf-8"))
        rows, key = build_review(claude, muse, pr.ai_fields(), options["seed"])
        out = Path(options["out_dir"])
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "review.csv", "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["organisation"])
            writer.writeheader()
            writer.writerows(rows)
        (out / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
        (out / "README.txt").write_text(REVIEW_README, encoding="utf-8")
        self.stdout.write(f"{len(rows)} rows to mark in {out / 'review.csv'}. Keep key.json away from the reviewers.")

    def _score(self, options):
        claude = json.loads(Path(options["claude"]).read_text(encoding="utf-8")) if options["claude"] else []
        muse = json.loads(Path(options["muse"]).read_text(encoding="utf-8"))
        key = json.loads(Path(options["key"]).read_text(encoding="utf-8"))
        with open(options["review"], newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        summary = score(rows, key, claude, muse, len(pr.ai_fields()))
        for arm in ("claude", "muse"):
            if summary[arm] is not None:
                self.stdout.write(f"{arm}: " + ", ".join(f"{k}={v}" for k, v in summary[arm].items()))
        self.stdout.write("\nProposed thresholds (for the supervisors to confirm):")
        results = thresholds(summary)
        for label, ok, detail in results:
            self.stdout.write(f"  {'INFO' if ok is None else 'PASS' if ok else 'FAIL'}  {label}  ({detail})")
        judged = [r[1] for r in results if r[1] is not None]
        if summary["claude"] is None:
            self.stdout.write(self.style.SUCCESS("Muse alone passes its absolute checks. Compare it with Claude before deciding.")
                              if all(judged) else self.style.WARNING("Muse fails an absolute check. Do not use it for PROIT on this evidence."))
        else:
            self.stdout.write(self.style.SUCCESS("All thresholds met: Muse is worth a larger confirmatory run.") if all(judged)
                              else self.style.WARNING("Not all thresholds met: do not switch PROIT to Muse on this evidence."))
