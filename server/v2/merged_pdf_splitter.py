"""
merged_pdf_splitter.py
Splits a merged PDF containing multiple resumes into individual candidate segments.

Uses Gemini Flash for single-pass page classification: each page is classified by
document type, whether it starts a new document, candidate name, and confidence.
This replaces the two-pass approach in amalgam_parser.py with a simpler, cheaper design.
"""

import json
import pymupdf
import tempfile
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from google import genai
from v2.gemini_client import get_gemini_client
from v2.cross_reference.config import LLM_MODEL

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class PageClassification:
    page_index: int
    document_type: str          # "resume" | "cover_letter" | "transcript" | "other"
    is_document_start: bool
    confidence: float           # 0.0-1.0
    candidate_name: str | None


@dataclass
class CandidateSegment:
    candidate_name: str
    page_range: tuple[int, int]   # (start, end) inclusive
    document_type: str
    confidence: float             # min confidence across pages in segment
    pdf_bytes: bytes = field(default=b"", repr=False)


@dataclass
class SplitResult:
    segments: list[CandidateSegment]
    discarded_pages: list[PageClassification]
    duplicates_removed: list[dict]    # {name, kept_range, discarded_ranges}
    warnings: list[str]


# ── Gemini page upload/cleanup ───────────────────────────────────────────────


async def _upload_pages(client: genai.Client, files: list[Path]) -> list[genai.types.File]:
    """Upload all single-page PDFs to Gemini file API in parallel."""
    tasks = [client.aio.files.upload(file=path) for path in files]
    return await asyncio.gather(*tasks)


async def _delete_pages(client: genai.Client, handles: list[genai.types.File]):
    """Delete all uploaded page handles from Gemini."""
    tasks = [client.aio.files.delete(name=h.name) for h in handles]
    await asyncio.gather(*tasks)


# ── Single-pass page classification ─────────────────────────────────────────


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "enum": ["resume", "cover_letter", "transcript", "other"],
        },
        "is_document_start": {"type": "boolean"},
        "confidence": {"type": "number"},
        "candidate_name": {"type": "string"},
    },
    "required": ["document_type", "is_document_start", "confidence", "candidate_name"],
}

SYSTEM_INSTRUCTION = (
    "You are a document classifier analyzing individual pages extracted from a "
    "multi-document PDF that may contain resumes, cover letters, transcripts, "
    "and other materials. For each page, determine its document type, whether it "
    "starts a new document, your confidence level, and the candidate's full name."
)

USER_PROMPT = (
    "Analyze this page from a multi-document PDF.\n\n"
    "Respond with JSON only using this schema:\n"
    "{\n"
    '  "document_type": "resume" | "cover_letter" | "transcript" | "other",\n'
    '  "is_document_start": true/false,\n'
    '  "confidence": 0.0-1.0,\n'
    '  "candidate_name": "Full Name" or ""\n'
    "}\n\n"
    "Rules:\n"
    "- A resume typically starts with a candidate name, contact info, and sections "
    "like Summary, Skills, Experience, Education.\n"
    "- A cover letter starts with a greeting (Dear...) or discusses interest in a position.\n"
    "- A transcript contains course listings, GPAs, or academic records.\n"
    '- "other" = anything that doesn\'t fit the above categories.\n'
    "- is_document_start = true if this page begins a NEW document (not a continuation "
    "of the previous page's document).\n"
    "- confidence = how confident you are in your classification (0.0 = uncertain, 1.0 = certain).\n"
    "- candidate_name = the person's full name if visible on this page. Look at the top "
    'of resumes for names. Use "" if not visible.'
)


async def _classify_page(
    client: genai.Client,
    page_handle: genai.types.File,
    page_index: int,
) -> PageClassification:
    """Classify a single page using Gemini Flash."""
    response = await client.aio.models.generate_content(
        model=LLM_MODEL,
        contents=[page_handle, USER_PROMPT],
        config=genai.types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=200,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=CLASSIFICATION_SCHEMA,
        ),
    )
    result = json.loads(response.text)
    return PageClassification(
        page_index=page_index,
        document_type=result.get("document_type", "other"),
        is_document_start=result.get("is_document_start", False),
        confidence=float(result.get("confidence", 0.0)),
        candidate_name=result.get("candidate_name") or None,
    )


# ── Grouping, filtering, deduplication ───────────────────────────────────────


def normalize_name(name: str | None) -> str:
    """Lowercase, collapse whitespace, strip."""
    if not name:
        return ""
    return " ".join(name.lower().split())


def _group_pages_into_segments(
    classifications: list[PageClassification],
) -> list[dict]:
    """
    Group consecutive pages between document starts into segments.
    Returns list of {start, end, document_type, confidence, candidate_name}.
    """
    if not classifications:
        return []

    segments: list[dict] = []
    current_start = 0
    current_type = classifications[0].document_type
    current_name = classifications[0].candidate_name
    current_confidences = [classifications[0].confidence]

    for i in range(1, len(classifications)):
        page = classifications[i]
        if page.is_document_start:
            # Close previous segment
            segments.append({
                "start": current_start,
                "end": i - 1,
                "document_type": current_type,
                "confidence": min(current_confidences),
                "candidate_name": current_name,
            })
            # Start new segment
            current_start = i
            current_type = page.document_type
            current_name = page.candidate_name
            current_confidences = [page.confidence]
        else:
            current_confidences.append(page.confidence)
            # If we see a name on a continuation page and didn't have one, pick it up
            if not current_name and page.candidate_name:
                current_name = page.candidate_name

    # Close final segment
    segments.append({
        "start": current_start,
        "end": len(classifications) - 1,
        "document_type": current_type,
        "confidence": min(current_confidences),
        "candidate_name": current_name,
    })

    return segments


def _deduplicate_segments(
    segments: list[CandidateSegment],
) -> tuple[list[CandidateSegment], list[dict]]:
    """
    Deduplicate segments by normalized candidate name.
    Keeps the segment with the most pages (tiebreak: highest confidence).
    Returns (deduplicated_segments, duplicates_info).
    """
    from collections import defaultdict

    name_groups: dict[str, list[CandidateSegment]] = defaultdict(list)
    unnamed: list[CandidateSegment] = []

    for seg in segments:
        norm = normalize_name(seg.candidate_name)
        if not norm:
            unnamed.append(seg)
        else:
            name_groups[norm].append(seg)

    deduped: list[CandidateSegment] = list(unnamed)
    duplicates_info: list[dict] = []

    for norm_name, group in name_groups.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        # Sort: most pages first, then highest confidence
        group.sort(
            key=lambda s: (s.page_range[1] - s.page_range[0] + 1, s.confidence),
            reverse=True,
        )
        kept = group[0]
        discarded = group[1:]
        deduped.append(kept)
        duplicates_info.append({
            "name": kept.candidate_name,
            "kept_range": list(kept.page_range),
            "discarded_ranges": [list(s.page_range) for s in discarded],
        })

    # Sort by page range for consistent ordering
    deduped.sort(key=lambda s: s.page_range[0])
    return deduped, duplicates_info


# ── PDF byte extraction ──────────────────────────────────────────────────────


def _extract_segment_bytes(
    amalgam_pdf: pymupdf.Document, start: int, end: int
) -> bytes:
    """Extract pages [start, end] inclusive from amalgam_pdf as new PDF bytes."""
    with pymupdf.open() as doc:
        doc.insert_pdf(amalgam_pdf, from_page=start, to_page=end)
        return doc.tobytes()


# ── Main entry point ─────────────────────────────────────────────────────────


async def split_merged_pdf(pdf_bytes: bytes) -> SplitResult:
    """
    Split a merged PDF into individual candidate resume segments.
    Uses Gemini Flash for page classification.
    Returns deduplicated segments with extracted PDF bytes.
    """
    client = get_gemini_client()
    warnings: list[str] = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as amalgam_pdf:
        total_pages = len(amalgam_pdf)
        logger.info(f"Splitting merged PDF: {total_pages} pages")

        if total_pages == 0:
            return SplitResult(segments=[], discarded_pages=[], duplicates_removed=[], warnings=["PDF has no pages"])

        # 1. Split into single-page PDFs in temp dir and upload to Gemini
        page_handles: list[genai.types.File] = []
        with tempfile.TemporaryDirectory() as tempdir_str:
            tempdir = Path(tempdir_str)
            page_files: list[Path] = []

            for i in range(total_pages):
                page_path = tempdir / f"page-{i}.pdf"
                with pymupdf.open() as staging:
                    staging.insert_pdf(amalgam_pdf, from_page=i, to_page=i)
                    staging.save(str(page_path))
                page_files.append(page_path)

            logger.info(f"Uploading {total_pages} pages to Gemini for classification")
            page_handles = await _upload_pages(client, page_files)

            # 2. Classify all pages in parallel
            classify_tasks = [
                _classify_page(client, page_handles[i], i)
                for i in range(total_pages)
            ]
            classifications: list[PageClassification] = await asyncio.gather(*classify_tasks)

        # 3. Clean up Gemini file uploads
        try:
            await _delete_pages(client, page_handles)
        except Exception as e:
            logger.warning(f"Failed to clean up Gemini file uploads: {e}")

        # 4. Group pages into segments
        raw_segments = _group_pages_into_segments(classifications)
        logger.info(f"Found {len(raw_segments)} document segments")

        # 5. Filter: keep only resumes, track discarded
        discarded_pages: list[PageClassification] = []
        resume_segments: list[dict] = []

        for seg in raw_segments:
            if seg["document_type"] == "resume":
                resume_segments.append(seg)
            else:
                # Add all pages in this non-resume segment to discarded
                for pi in range(seg["start"], seg["end"] + 1):
                    discarded_pages.append(classifications[pi])

        if not resume_segments:
            warnings.append("No resume segments detected in the PDF")

        logger.info(
            f"Kept {len(resume_segments)} resume segments, "
            f"discarded {len(discarded_pages)} non-resume pages"
        )

        # 6. Extract PDF bytes for each resume segment
        candidate_segments: list[CandidateSegment] = []
        for seg in resume_segments:
            pdf_bytes_segment = _extract_segment_bytes(
                amalgam_pdf, seg["start"], seg["end"]
            )
            candidate_segments.append(CandidateSegment(
                candidate_name=seg["candidate_name"] or f"Unknown_p{seg['start'] + 1}",
                page_range=(seg["start"], seg["end"]),
                document_type="resume",
                confidence=seg["confidence"],
                pdf_bytes=pdf_bytes_segment,
            ))

        # 7. Deduplicate by candidate name
        deduped, duplicates_info = _deduplicate_segments(candidate_segments)
        if duplicates_info:
            logger.info(f"Deduplicated {len(duplicates_info)} candidate(s)")
            for dup in duplicates_info:
                warnings.append(
                    f"Duplicate found: {dup['name']} — kept pages "
                    f"{dup['kept_range']}, discarded {dup['discarded_ranges']}"
                )

        return SplitResult(
            segments=deduped,
            discarded_pages=discarded_pages,
            duplicates_removed=duplicates_info,
            warnings=warnings,
        )
