"""Checks that the configured document-coding provider can do the three things the portal relies on.

Uses only synthetic content made here (a number, and a one-page invoice PDF), never study data, so it is safe
to run against a new provider before any real document is sent to it. Prints the provider host and model, never
a key. Exits non-zero if any check fails, so a script can refuse to switch provider on a failure.
"""

import base64
import io
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from reportlab.pdfgen import canvas

from apps.evidence.ai_coding import (
    ai_coding_is_configured,
    call_with_tool_choice_fallback,
    coding_client,
    coding_provider,
    forced_tool_choice,
    stream_final,
)

TOOL = {
    "name": "report_number",
    "description": "Report the number that was asked for.",
    "input_schema": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
}


def _invoice_pdf() -> bytes:
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(72, 720, "Invoice INV-7731")
    page.drawString(72, 700, "Total due: 4821 dollars")
    page.save()
    return buffer.getvalue()


def _value(response):
    block = next((b for b in response.content if b.type == "tool_use"), None)
    return None if block is None else dict(block.input).get("value")


# The same request path the portal uses (ai_coding), so a pass here means drafting will work.
def _plain(client, model):
    return call_with_tool_choice_fallback(
        client.messages.create, model=model, max_tokens=200, tools=[TOOL], tool_choice=forced_tool_choice("report_number"),
        messages=[{"role": "user", "content": "The number is 17. Report it by calling report_number."}],
    )


def _streamed(client, model, content="The number is 17. Report it by calling report_number."):
    return call_with_tool_choice_fallback(
        lambda **kw: stream_final(client, **kw), model=model, max_tokens=200, tools=[TOOL],
        tool_choice=forced_tool_choice("report_number"), messages=[{"role": "user", "content": content}],
    )


def _pdf(client, model):
    data = base64.standard_b64encode(_invoice_pdf()).decode()
    content = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
        {"type": "text", "text": "Read the attached document and report the total due as a whole number by calling report_number."},
    ]
    return _streamed(client, model, content)


CHECKS = [
    ("forced tool answer (the document-details call)", _plain, 17),
    ("forced tool answer, streamed (the coding call)", _streamed, 17),
    ("PDF attachment read correctly", _pdf, 4821),
]


PROIT_QUESTION = "Search the web: in which year did Zimbabwe become independent? Then call report_number with that year."


class Command(BaseCommand):
    help = "Check the configured document-coding provider (or, with --proit, PROIT's) using synthetic content only."

    def add_arguments(self, parser):
        parser.add_argument("--proit", action="store_true", help="Check PROIT's Meta provider: web search plus an answer in the required format.")

    def handle(self, *args, **options):
        if options["proit"]:
            return self._proit()
        if not ai_coding_is_configured():
            raise CommandError("No API key is configured for document coding.")
        client = coding_client(timeout=120.0)
        model = settings.AI_DOCUMENT_CODING_MODEL
        self.stdout.write(f"Provider: {coding_provider()}   Model: {model}")
        failed = 0
        for name, run, expected in CHECKS:
            started = time.monotonic()
            try:
                response = run(client, model)
                got = _value(response)
                usage = getattr(response, "usage", None)
                tokens = f"{getattr(usage, 'input_tokens', '?')} in / {getattr(usage, 'output_tokens', '?')} out"
                ok, note = got == expected, f"expected {expected}, got {got}"
            except Exception as exc:  # a diagnostic: any failure is a result, not a crash
                ok, tokens, note = False, "-", f"{type(exc).__name__}: {str(exc)[:200]}"
            failed += 0 if ok else 1
            self.stdout.write(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s, {tokens})" + ("" if ok else f"\n        {note}"))
        if failed:
            raise CommandError(f"{failed} of {len(CHECKS)} checks failed. Do not switch to this provider yet.")
        self.stdout.write(self.style.SUCCESS(f"All {len(CHECKS)} checks passed."))

    def _proit(self):
        from apps.proit import muse
        from apps.proit.ai_research import ai_research_is_configured, proit_provider

        if proit_provider() != "meta":
            raise CommandError("PROIT is set to Anthropic, so there is no Meta provider to check.")
        if not ai_research_is_configured():
            raise CommandError("No AI_PROIT_API_KEY is configured.")
        key, model = settings.AI_PROIT_API_KEY.strip(), settings.AI_PROIT_RESEARCH_MODEL
        self.stdout.write(f"Provider: api.meta.ai (Responses API)   Model: {model}")
        body = {"model": model, "input": PROIT_QUESTION, "tools": [{"type": "web_search"}, {"type": "function", **{k: TOOL[k] for k in ("name", "description")}, "parameters": TOOL["input_schema"]}],
                "include": ["web_search_call.results"], "max_output_tokens": 2000}
        started, urls, searches, call, tokens = time.monotonic(), set(), 0, None, [0, 0]
        try:
            for _turn in range(3):
                response = muse.post_responses(key, body)
                output = response.get("output") or []
                urls |= muse.muse_urls(output)
                searches += muse.muse_search_count(output)
                used = response.get("usage") or {}
                tokens[0] += used.get("input_tokens", 0) or 0
                tokens[1] += used.get("output_tokens", 0) or 0
                call = muse.muse_function_call(output, "report_number")
                if call:
                    break
                body = {**body, "previous_response_id": response.get("id"), "input": "Now call report_number with the year."}
        except Exception as exc:  # a diagnostic: any failure (refused key, region, network) is a result, not a crash
            raise CommandError(f"The request failed: {type(exc).__name__}: {str(exc)[:300]}") from exc
        value = call[1].get("value") if call else None
        results = [
            ("answer returned in the required format", call is not None, f"got {call}" if call is None else ""),
            ("searched the web and returned source URLs", searches > 0 and bool(urls), f"{searches} searches, {len(urls)} URLs"),
            ("answer taken correctly from the search", value == 1980, f"expected 1980, got {value}"),
        ]
        self.stdout.write(f"  ({time.monotonic() - started:.1f}s, {tokens[0]} in / {tokens[1]} out, {searches} searches)")
        for name, ok, note in results:
            self.stdout.write(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n        {note}"))
        failed = sum(1 for _n, ok, _x in results if not ok)
        if failed:
            raise CommandError(f"{failed} of {len(results)} PROIT checks failed. Do not switch PROIT to Meta yet.")
        self.stdout.write(self.style.SUCCESS(f"All {len(results)} PROIT checks passed."))
