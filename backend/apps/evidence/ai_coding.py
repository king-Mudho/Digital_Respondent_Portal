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
import io
import re
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

# Claude reads at most this many pages of a PDF per request; a longer
# document (e.g. a 648-page national strategy) has to be read in a chosen
# page range -- which is also how a person would code it: one evidence unit
# at a time, not a whole strategy at once.
MAX_PDF_PAGES = 100

# Claude's tool schema only allows [a-zA-Z0-9_.-] in a property name, so a
# form path like "section_a/DOC_ID" is sent as "section_a__DOC_ID" and mapped
# back afterwards. (The first real call, 2026-09-19, was rejected for the
# "/" -- a mocked test can't see that, so test_tool_schema_property_names_are_
# valid checks the pattern the API enforces.)
_PATH_SEP = "__"
_TOOL_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")


def _to_tool_key(path: str) -> str:
    return path.replace("/", _PATH_SEP)


def _from_tool_key(key: str) -> str:
    return key.replace(_PATH_SEP, "/")


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
        key = field["name"] if field["in_repeat"] else _to_tool_key(field["path"])
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

    properties[_to_tool_key("section_j/metric_repeat")] = {
        "type": "array",
        "description": "One entry per quantitative metric found in the document. Leave empty if none.",
        "items": {"type": "object", "properties": repeat_items},
    }
    return {
        "name": "submit_document_coding",
        "description": "Records a draft coding of the source document against the ABF-FST Document Analysis Tool.",
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


def parse_page_range(text: str, total_pages: int) -> tuple[int, int]:
    """'12-60' or '12' -> (12, 60) / (12, 12), 1-based and inclusive."""
    match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", text or "")
    if not match:
        raise AIDraftError("invalid_page_range", "Enter pages like 1-100, or a single page number.")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start or end > total_pages:
        raise AIDraftError(
            "invalid_page_range", f"That page range is outside this PDF, which has {total_pages} pages.",
        )
    if end - start + 1 > MAX_PDF_PAGES:
        raise AIDraftError(
            "page_range_too_long",
            f"The AI can read at most {MAX_PDF_PAGES} pages at a time; that range is {end - start + 1}.",
        )
    return start, end


def pdf_page_count(abs_path: str) -> int | None:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        return len(PdfReader(abs_path).pages)
    except (PyPdfError, OSError, ValueError):
        return None


def _read_file_block(abs_path: str, content_type: str, page_range: str = "") -> tuple[dict, str]:
    """Returns (content block, plain-English description of what was sent),
    the description going into the prompt so the model cites original page
    numbers, not the numbers within a trimmed excerpt."""
    ext = Path(abs_path).suffix.lower()
    media_type = NATIVE_MEDIA_TYPES.get(ext) or (content_type if content_type in NATIVE_MEDIA_TYPES.values() else None)
    if not media_type:
        raise AIDraftError(
            "unsupported_file_type",
            f"AI drafting doesn't support '{ext or 'this'}' files yet -- only PDF, JPG and PNG source files.",
        )
    if media_type != "application/pdf":
        data = base64.standard_b64encode(Path(abs_path).read_bytes()).decode("ascii")
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}, "an image"

    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(abs_path)
        total = len(reader.pages)
    except (PyPdfError, OSError, ValueError) as exc:
        raise AIDraftError("unreadable_pdf", "That PDF couldn't be opened -- it may be damaged or password-protected.") from exc

    if total <= MAX_PDF_PAGES and not page_range.strip():
        data = base64.standard_b64encode(Path(abs_path).read_bytes()).decode("ascii")
        block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
        return block, f"the whole document ({total} pages)"

    if not page_range.strip():
        raise AIDraftError(
            "pdf_too_long",
            f"This PDF has {total} pages, and the AI can read at most {MAX_PDF_PAGES} at a time. "
            "Enter the pages that make up this evidence unit (for example 1-100).",
        )
    start, end = parse_page_range(page_range, total)
    writer = PdfWriter()
    for index in range(start - 1, end):
        writer.add_page(reader.pages[index])
    buffer = io.BytesIO()
    writer.write(buffer)
    data = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
    block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    return block, (
        f"pages {start}-{end} of a {total}-page document; page 1 of the attachment is page {start} of the original, "
        "so give locators using the original page and paragraph numbers"
    )


def generate_draft(
    document: DocumentRecord, *, source_path: str, source_content_type: str, user, page_range: str = "",
) -> dict:
    """Calls Claude on the document's uploaded source file and returns a
    draft answer dict keyed by field path (repeat answers under
    "section_j/metric_repeat" as a list of dicts). Does not save anything
    to KoboToolbox -- callers persist the draft on DocumentRecord.ai_draft
    for the RA to review (tasks.py). Slow (an AI reading the whole
    document), so it only ever runs in the background."""
    if not ai_coding_is_configured():
        raise AIDraftError("ai_not_configured", "AI drafting hasn't been set up (ANTHROPIC_API_KEY).", 503)

    file_block, sent = _read_file_block(source_path, source_content_type, page_range)
    tool = _tool_schema()

    field_list = "\n".join(
        f"- {_to_tool_key(f['path']) if not f['in_repeat'] else f['name']} ({f['type']}"
        + (f", choices: {[c['code'] for c in f['choices']]}" if f.get("choices") else "")
        + f"): {f['label']}"
        for f in SCHEMA["fields"]
        if f["path"] not in DETERMINISTIC_FIELDS
    )
    prompt = (
        "You are drafting a documentary evidence coding for an academic study "
        "(ABF-FST: Agribusiness Bankability Framework for Food Systems Transformation, Zimbabwe). "
        f"The source document is titled \"{document.title}\"" +
        (f" by {document.author_or_speaker}" if document.author_or_speaker else "") + f". You are given {sent}.\n\n"
        "Read the attached document and call submit_document_coding with your best draft answer for every "
        "field below, grounded in what the document actually says. Use exact page/paragraph locators wherever "
        "the source gives them. Where the document doesn't support a field, say so plainly in the relevant "
        "text field rather than guessing, and prefer a lower evidence-strength rating over an unsupported high "
        "one -- this is a draft a human researcher will check, not a final judgment, so it should show real "
        "variation in strength/support ratings rather than defaulting everything to the most favourable option.\n\n"
        f"Fields to answer:\n{field_list}"
    )

    # 10 minutes: reading a long document and writing ~110 fields is slow.
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=600.0)
    try:
        response = client.messages.create(
            model=settings.AI_DOCUMENT_CODING_MODEL,
            max_tokens=16000,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_document_coding"},
            messages=[{"role": "user", "content": [file_block, {"type": "text", "text": prompt}]}],
        )
    except anthropic.APIError as exc:
        raise AIDraftError("ai_request_failed", f"The AI request failed: {exc}", 502) from exc

    if response.stop_reason == "max_tokens":
        # A cut-off answer is missing fields; never save it as a draft.
        raise AIDraftError("ai_answer_cut_off", "The AI's answer was cut off before it finished. Try a narrower page range.", 502)
    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise AIDraftError("ai_no_answer", "The AI didn't return a coding draft.", 502)

    draft = {_from_tool_key(key): value for key, value in dict(tool_use.input).items()}
    for path, resolver in DETERMINISTIC_FIELDS.items():
        draft[path] = resolver(document)
    draft["_generated_at"] = timezone.now().isoformat()
    draft["_generated_by_model"] = settings.AI_DOCUMENT_CODING_MODEL
    draft["_generated_by_user_id"] = getattr(user, "id", None)
    if page_range.strip():
        draft["_source_pages"] = page_range.strip()
    return draft
