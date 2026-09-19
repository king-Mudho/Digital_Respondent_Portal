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

# Output budget for the ~110-field answer. The first real run (NDS2, 2026-09-19)
# was cut off at 16,000 tokens; Opus 5 allows 128,000.
MAX_OUTPUT_TOKENS = 64000

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



# --- Reading other file types -------------------------------------------------

# The API rejects a whole request over ~32 MB, and base64 adds a third.
MAX_REQUEST_BYTES = 30 * 1024 * 1024
# The API rejects any single image over 5 MB.
MAX_IMAGE_BYTES = int(4.5 * 1024 * 1024)
MAX_TEXT_CHARS = 2_500_000  # ~600k tokens, inside the model's 1M-token window


def _pdf_payload(raw: bytes) -> str:
    data = base64.standard_b64encode(raw).decode("ascii")
    if len(data) > MAX_REQUEST_BYTES:
        raise AIDraftError(
            "file_too_big_for_ai",
            "That PDF is too large for the AI to read as it is. Enter a narrower page range, "
            "or upload a smaller version of the file.",
        )
    return data


def _prepare_image(abs_path: str, media_type: str) -> tuple[str, str]:
    """Phone photos of documents are routinely over the API's 5 MB image limit:
    shrink and re-encode as JPEG until they fit, keeping them legible."""
    raw = Path(abs_path).read_bytes()
    if len(raw) <= MAX_IMAGE_BYTES:
        return base64.standard_b64encode(raw).decode("ascii"), media_type
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise AIDraftError("unreadable_image", "That image couldn't be opened.") from exc
    image = image.convert("RGB")
    image.thumbnail((3000, 3000))
    for quality in (85, 75, 65, 50):
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=quality)
        if out.tell() <= MAX_IMAGE_BYTES:
            return base64.standard_b64encode(out.getvalue()).decode("ascii"), "image/jpeg"
    raise AIDraftError("file_too_big_for_ai", "That image is too large to read even after shrinking it.")


def _docx_text(abs_path: str) -> str:
    import zipfile
    from xml.etree import ElementTree

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(abs_path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
        raise AIDraftError("unreadable_document", "That Word file couldn't be opened -- try saving it as a PDF.") from exc
    lines = []
    for paragraph in root.iter(f"{ns}p"):
        text = "".join(t.text or "" for t in paragraph.iter(f"{ns}t"))
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def _xlsx_text(abs_path: str) -> str:
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(abs_path, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a zoo of types for a bad file
        raise AIDraftError("unreadable_document", "That Excel file couldn't be opened -- try saving it as a PDF.") from exc
    parts = []
    for sheet in workbook.worksheets:
        parts.append(f"## Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(cells):
                parts.append("\t".join(cells))
    workbook.close()
    return "\n".join(parts)


def _plain_text(abs_path: str) -> str:
    return Path(abs_path).read_bytes().decode("utf-8", errors="replace")


TEXT_EXTRACTORS = {".docx": _docx_text, ".xlsx": _xlsx_text, ".txt": _plain_text, ".csv": _plain_text}
TEXT_EXTRACTOR_LABELS = {".docx": "Word document", ".xlsx": "Excel workbook", ".txt": "text file", ".csv": "CSV file"}


def _unsupported_message(ext: str) -> str:
    if ext in {".mp3", ".m4a", ".wav", ".mp4"}:
        return (
            "The AI can't listen to audio or video. Upload a transcript instead "
            "(a PDF, Word or text file), and keep the recording as the source reference."
        )
    if ext in {".doc", ".xls"}:
        return f"The AI can't read old-format '{ext}' files. Save it as a PDF or as a newer .docx/.xlsx and upload that."
    return f"AI drafting doesn't support '{ext or 'this'}' files. It reads PDF, Word, Excel, text and image (JPG/PNG) files."


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
    if ext in TEXT_EXTRACTORS:
        text = TEXT_EXTRACTORS[ext](abs_path)
        if not text.strip():
            raise AIDraftError("empty_document", "No readable text was found in that file.")
        if len(text) > MAX_TEXT_CHARS:
            raise AIDraftError(
                "document_too_long",
                "That document is too long for the AI to read in one go. Split it, or upload the part you want coded.",
            )
        return (
            {"type": "text", "text": f"<document>\n{text}\n</document>"},
            f"the full text of a {TEXT_EXTRACTOR_LABELS[ext]} (it has no page numbers, so cite headings, "
            "paragraph or section numbers, or sheet names as locators)",
        )
    media_type = NATIVE_MEDIA_TYPES.get(ext)
    if not media_type:
        raise AIDraftError("unsupported_file_type", _unsupported_message(ext))
    if media_type != "application/pdf":
        data, media_type = _prepare_image(abs_path, media_type)
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}, "an image"

    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(abs_path)
        total = len(reader.pages)
    except (PyPdfError, OSError, ValueError) as exc:
        raise AIDraftError("unreadable_pdf", "That PDF couldn't be opened -- it may be damaged or password-protected.") from exc

    if total <= MAX_PDF_PAGES and not page_range.strip():
        data = _pdf_payload(Path(abs_path).read_bytes())
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
    data = _pdf_payload(buffer.getvalue())
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
        "variation in strength/support ratings rather than defaulting everything to the most favourable option. "
        "Keep every free-text field focused: a few sentences with the key locator, not a full essay.\n\n"
        f"Fields to answer:\n{field_list}"
    )

    # 15 minutes: reading a long document and writing ~110 fields is slow.
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=900.0)
    try:
        # Streamed: the SDK refuses a non-streaming request with a large
        # output budget, and a full answer runs to tens of thousands of tokens
        # (16,000 cut the first real NDS2 draft off; the model allows 128,000).
        with client.messages.stream(
            model=settings.AI_DOCUMENT_CODING_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_document_coding"},
            messages=[{"role": "user", "content": [file_block, {"type": "text", "text": prompt}]}],
        ) as stream:
            response = stream.get_final_message()
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
    usage = getattr(response, "usage", None)
    for attr, key in (("input_tokens", "_tokens_in"), ("output_tokens", "_tokens_out")):
        value = getattr(usage, attr, None)
        if isinstance(value, int):  # what this draft cost, for the PI's billing
            draft[key] = value
    if page_range.strip():
        draft["_source_pages"] = page_range.strip()
    return draft
