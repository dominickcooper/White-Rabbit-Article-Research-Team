from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

import pymupdf
from docx import Document

from white_rabbit.local_sources import read_local_document


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    page_number: int | None = None
    page_label: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class PreparedSource:
    text: str
    spans: list[SourceSpan]
    unreadable: list[str]


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    ordinal: int
    text: str
    source_start: int
    source_end: int
    locator: dict
    text_hash: str


def prepare_source(path: Path) -> PreparedSource:
    path = path.resolve()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        parts, spans, unreadable, cursor = [], [], [], 0
        with pymupdf.open(path) as document:
            for index, page in enumerate(document):
                text = page.get_text("text")
                label = page.get_label() or str(index + 1)
                if not text.strip():
                    unreadable.append(f"PDF page {index + 1} ({label}) contained no extractable text")
                if parts:
                    separator = "\n\f\n"
                    parts.append(separator); cursor += len(separator)
                start = cursor; parts.append(text); cursor += len(text)
                spans.append(SourceSpan(start, cursor, page_number=index + 1, page_label=label))
        return PreparedSource("".join(parts), spans, unreadable)
    if suffix == ".docx":
        document = Document(path)
        parts, spans, cursor, section = [], [], 0, None
        for index, paragraph in enumerate(document.paragraphs, start=1):
            if paragraph.style and paragraph.style.name.lower().startswith("heading") and paragraph.text.strip():
                section = paragraph.text.strip()
            text = paragraph.text + "\n"
            start = cursor; parts.append(text); cursor += len(text)
            spans.append(SourceSpan(start, cursor, line_start=index, line_end=index, section=section))
        return PreparedSource("".join(parts), spans, [])
    local = read_local_document(path)
    spans, cursor, section = [], 0, None
    for line_number, line in enumerate(local.text.splitlines(keepends=True), start=1):
        if suffix in {".md", ".markdown"} and re.match(r"^#{1,6}\s+\S", line):
            section = re.sub(r"^#{1,6}\s+", "", line).strip()
        spans.append(SourceSpan(cursor, cursor + len(line), line_start=line_number, line_end=line_number, section=section))
        cursor += len(line)
    if cursor < len(local.text):
        spans.append(SourceSpan(cursor, len(local.text), line_start=len(spans) + 1, line_end=len(spans) + 1))
    return PreparedSource(local.text, spans, ["source contained no readable text"] if not local.text.strip() else [])


def chunk_source(prepared: PreparedSource, document_hash: str, *, chunk_size: int = 12000,
                 overlap: int = 1000, max_chunks: int | None = None) -> list[DocumentChunk]:
    if chunk_size < 500 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be >=500 and overlap must be smaller than chunk_size")
    text, chunks, start, ordinal = prepared.text, [], 0, 0
    while start < len(text) and (max_chunks is None or ordinal < max_chunks):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = max(text.rfind("\n\n", start + chunk_size // 2, end), text.rfind("\n", start + chunk_size // 2, end))
            if boundary > start:
                end = boundary + 1
        chunk_text = text[start:end]
        digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        stable = hashlib.sha256(f"{document_hash}:{start}:{end}:{digest}".encode()).hexdigest()[:24]
        overlapping = [span for span in prepared.spans if span.end > start and span.start < end]
        locator = {
            "source_start": start, "source_end": end,
            "page_start": next((span.page_number for span in overlapping if span.page_number), None),
            "page_end": next((span.page_number for span in reversed(overlapping) if span.page_number), None),
            "page_labels": list(dict.fromkeys(span.page_label for span in overlapping if span.page_label)),
            "line_start": next((span.line_start for span in overlapping if span.line_start), None),
            "line_end": next((span.line_end for span in reversed(overlapping) if span.line_end), None),
            "sections": list(dict.fromkeys(span.section for span in overlapping if span.section)),
            "segments": [
                {"source_start": span.start, "source_end": span.end, "page_number": span.page_number,
                 "page_label": span.page_label, "line_start": span.line_start, "line_end": span.line_end,
                 "section": span.section}
                for span in overlapping
            ],
        }
        chunks.append(DocumentChunk(f"CHK-{stable}", ordinal, chunk_text, start, end, locator, digest))
        ordinal += 1
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def locate_passage(chunk: DocumentChunk, passage: str, suggested_start: int | None = None) -> tuple[dict, bool, bool]:
    """Return recoverable locator, found flag, and ambiguity flag."""
    positions, offset = [], 0
    while passage:
        found = chunk.text.find(passage, offset)
        if found < 0:
            break
        positions.append(found); offset = found + 1
    if not positions:
        locator = {**chunk.locator, "chunk_id": chunk.id, "locator_incomplete": True}
        locator.pop("segments", None)
        return locator, False, False
    relative = suggested_start if suggested_start in positions else positions[0]
    absolute = chunk.source_start + relative
    result = {
        **chunk.locator, "chunk_id": chunk.id, "chunk_ordinal": chunk.ordinal,
        "source_start": absolute, "source_end": absolute + len(passage),
        "chunk_start": relative, "chunk_end": relative + len(passage),
        "locator_incomplete": False,
    }
    passage_segments = [
        segment for segment in chunk.locator.get("segments", [])
        if segment["source_end"] > absolute and segment["source_start"] < absolute + len(passage)
    ]
    if passage_segments:
        result["page_number"] = next((segment["page_number"] for segment in passage_segments if segment["page_number"]), None)
        result["page_label"] = next((segment["page_label"] for segment in passage_segments if segment["page_label"]), None)
        result["line_start"] = next((segment["line_start"] for segment in passage_segments if segment["line_start"]), None)
        result["line_end"] = next((segment["line_end"] for segment in reversed(passage_segments) if segment["line_end"]), None)
        result["section"] = next((segment["section"] for segment in passage_segments if segment["section"]), None)
    result.pop("segments", None)
    return result, True, len(positions) > 1 and suggested_start not in positions
