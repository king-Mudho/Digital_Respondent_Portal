"""
AI-assisted drafting for the Document, Digital Platform & Media Analysis
Tool (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md).

DELIBERATELY A DRAFT, NEVER A SUBMISSION: this module only ever produces an
editable draft (DocumentRecord.ai_draft) that a Documentary RA reviews and
can change before anything reaches KoboToolbox (kobo_submit.py, a separate
step the RA triggers explicitly). The ABI dimension ratings (Section D),
hypothesis-support codes (Section K) and evidence-strength judgments this
form captures ARE the study's documentary analysis method -- submitting an
AI's ratings as a completed coding record with nobody checking them would
mean the dissertation's qualitative analysis was produced by a machine and
presented as the researcher's own judgment. See docs/14 and the PI's
decision recorded 2026-09-17. Every draft is stamped with a model version
and a generated_at timestamp precisely so this is traceable in the
methodology write-up.

DETERMINISTIC FIELDS FIRST: DOC_ID, org_author, title_evidence_unit,
pub_event_date, url_file_platform and access_capture_date come straight
from the DocumentRecord/today's date, never from the AI -- there is no
reason to let a model re-derive facts the register already holds
correctly, and doing so risks a draft that disagrees with the record it's
attached to.
"""

import base64
from pathlib import Path

import anthropic
from django.conf import settings
from django.utils import timezone

from .document_tool_schema import SCHEMA
from .models import DocumentRecord

# Filled deterministically from the DocumentRecord -- never asked of the AI.
DETERMINISTIC_FIELDS = {
    "section_a/DOC_ID": lambda d: d.document_id,
    "section_a/org_author": lambda d: d.author_or_speaker,
    "section_a/title_evidence_unit": lambda d: d.title,
    "section_a/pub_event_date": lambda d: d.publication_or_event_date.isoformat() if d.publication_or_event_date else "",
    "section_a/url_file_platform": lambda d: d.source_url_or_reference,
    "section_a/access_capture_date": lambda d: timezone.now().date().isoformat(),
}

# Native Claude document/image support; anything else needs a text
# extraction path (added as the study actually uses those file types).
NATIVE_MEDIA_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class AIDraftError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def ai_coding_is_configured() -> bool:
    return bool((settings.ANTHROPIC_API_KEY or "").strip())


def _tool_schema() -> dict:
    """Builds the Claude tool-use JSON schema from document_tool_schema.json
    -- one property per non-deterministic, non-repeat field (enums for
    select_one/select_multiple, so the model can't return a choice code
    that doesn't exist on the live form), plus one array property for the
    Section J repeat group."""
    properties: dict = {}
    required: list[str] = []
    repeat_items: dict = {}

    for field in SCHEMA["fields"]:
        if field["path"] in DETERMINISTIC_FIELDS:
            continue
        target = repeat_items if field["in_repeat"] else properties
        key = field["name"] if field["in_repeat"] else field["path"]
        if field["type"] == "select_one":
            target[key] = {"type": "string", "enum": [c["code"] for c in field["choices"]],
                            "description": field["label"]}
        elif field["type"] == "select_multiple":
            target[key] = {"type": "array", "items": {"type": "string", "enum": [c["code"] for c in field["choices"]]},
                            "description": field["label"]}
        else:
            target[key] = {"type": "string", "description": field["label"]}
        if not field["in_repeat"]:
            required.append(key)

    properties["section_j/metric_repeat"] = {
        "type": "array",
        "description": "One entry per quantitative metric found in the document. Leave empty if none.",
        "items": {"type": "object", "properties": repeat_items},
    }
    return {
        "name": "submit_document_coding",
        "description": "Records a draft coding of the source document against the ABF-FST Document Analysis Tool.",
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


def _read_file_block(abs_path: str, content_type: str) -> dict:
    ext = Path(abs_path).suffix.lower()
    media_type = NATIVE_MEDIA_TYPES.get(ext) or (content_type if content_type in NATIVE_MEDIA_TYPES.values() else None)
    if not media_type:
        raise AIDraftError(
            "unsupported_file_type",
            f"AI drafting doesn't support '{ext or 'this'}' files yet -- only PDF, JPG and PNG source files.",
        )
    data = base64.standard_b64encode(Path(abs_path).read_bytes()).decode("ascii")
    block_type = "document" if media_type == "application/pdf" else "image"
    return {"type": block_type, "source": {"type": "base64", "media_type": media_type, "data": data}}


def generate_draft(document: DocumentRecord, *, source_path: str, source_content_type: str, user) -> dict:
    """Calls Claude on the document's uploaded source file and returns a
    draft answer dict keyed by field path (repeat answers under
    "section_j/metric_repeat" as a list of dicts). Does not save anything
    to KoboToolbox -- callers persist the draft on DocumentRecord.ai_draft
    for the RA to review (views.py)."""
    if not ai_coding_is_configured():
        raise AIDraftError("ai_not_configured", "AI drafting hasn't been set up (ANTHROPIC_API_KEY).", 503)

    file_block = _read_file_block(source_path, source_content_type)
    tool = _tool_schema()

    field_list = "\n".join(
        f"- {f['path']} ({f['type']}" + (f", choices: {[c['code'] for c in f['choices']]}" if f.get("choices") else "")
        + f"): {f['label']}"
        for f in SCHEMA["fields"]
        if f["path"] not in DETERMINISTIC_FIELDS
    )
    prompt = (
        "You are drafting a documentary evidence coding for an academic study "
        "(ABF-FST: Agribusiness Bankability Framework for Food Systems Transformation, Zimbabwe). "
        f"The source document is titled \"{document.title}\"" +
        (f" by {document.author_or_speaker}" if document.author_or_speaker else "") + ".\n\n"
        "Read the attached document and call submit_document_coding with your best draft answer for every "
        "field below, grounded in what the document actually says. Use exact page/paragraph locators wherever "
        "the source gives them. Where the document doesn't support a field, say so plainly in the relevant "
        "text field rather than guessing, and prefer a lower evidence-strength rating over an unsupported high "
        "one -- this is a draft a human researcher will check, not a final judgment, so it should show real "
        "variation in strength/support ratings rather than defaulting everything to the most favourable option.\n\n"
        f"Fields to answer:\n{field_list}"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=settings.AI_DOCUMENT_CODING_MODEL,
            max_tokens=8000,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_document_coding"},
            messages=[{"role": "user", "content": [file_block, {"type": "text", "text": prompt}]}],
        )
    except anthropic.APIError as exc:
        raise AIDraftError("ai_request_failed", f"The AI request failed: {exc}", 502) from exc

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise AIDraftError("ai_no_answer", "The AI didn't return a coding draft.", 502)

    draft = dict(tool_use.input)
    for path, resolver in DETERMINISTIC_FIELDS.items():
        draft[path] = resolver(document)
    draft["_generated_at"] = timezone.now().isoformat()
    draft["_generated_by_model"] = settings.AI_DOCUMENT_CODING_MODEL
    draft["_generated_by_user_id"] = getattr(user, "id", None)
    return draft
