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

from apps.evidence.ai_coding import ai_coding_is_configured, coding_client, coding_provider

TOOL = {
    "name": "report_number",
    "description": "Report the number that was asked for.",
    "input_schema": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
}
FORCED = {"type": "tool", "name": "report_number"}


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


def _plain(client, model):
    return client.messages.create(
        model=model, max_tokens=200, tools=[TOOL], tool_choice=FORCED,
        messages=[{"role": "user", "content": "The number is 17. Report it."}],
    )


def _streamed(client, model, content="The number is 17. Report it."):
    with client.messages.stream(
        model=model, max_tokens=200, tools=[TOOL], tool_choice=FORCED,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        return stream.get_final_message()


def _pdf(client, model):
    data = base64.standard_b64encode(_invoice_pdf()).decode()
    content = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
        {"type": "text", "text": "Read the attached document and report the total due as a whole number."},
    ]
    return _streamed(client, model, content)


CHECKS = [
    ("forced tool answer (the document-details call)", _plain, 17),
    ("forced tool answer, streamed (the coding call)", _streamed, 17),
    ("PDF attachment read correctly", _pdf, 4821),
]


class Command(BaseCommand):
    help = "Check the configured document-coding provider with synthetic content only."

    def handle(self, *args, **options):
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
