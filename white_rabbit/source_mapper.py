from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import AnchorMap

MARKER_RE = re.compile(r"\[\[(EV-\d{4,})\]\]")


@dataclass
class SourceRow:
    source_number: str
    phrase: str
    link: str
    evidence_id: str


def marker_contexts(article: str, radius: int = 350) -> dict[str, str]:
    contexts: dict[str, str] = {}
    for m in MARKER_RE.finditer(article):
        eid = m.group(1)
        if eid in contexts:
            continue
        left = max(0, m.start() - radius)
        right = min(len(article), m.end() + 80)
        contexts[eid] = article[left:right].replace("\n", " ")
    return contexts


def format_contexts(contexts: dict[str, str]) -> str:
    return "\n\n".join(f"{eid}: {ctx}" for eid, ctx in contexts.items())


def strip_markers(article: str) -> str:
    return MARKER_RE.sub("", article)


def _normalize_visible_markdown(text: str) -> str:
    # Anchor phrases may target visible text wrapped in bold/italics. The existing linker
    # can still match the underlying text, so verification checks raw and de-marked forms.
    return text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")


def _fallback_phrase(context: str, entities: list[str]) -> str:
    clean = MARKER_RE.sub("", context)
    for entity in sorted(entities, key=len, reverse=True):
        if entity and entity.lower() in clean.lower():
            idx = clean.lower().find(entity.lower())
            return clean[idx:idx + len(entity)]
    # Prefer identifiers/proper-noun sequences.
    patterns = [
        r"\b[A-Z]{2,}[A-Z0-9.-]*\b",
        r"\b(?:[A-Z][A-Za-z0-9&.'-]+\s+){1,4}[A-Z][A-Za-z0-9&.'-]+\b",
        r"\b[A-Z]{1,4}\d{2,}[A-Z0-9.-]*\b",
    ]
    for pat in patterns:
        hits = re.findall(pat, clean)
        if hits:
            return max(hits, key=len).strip()
    words = re.findall(r"\b[\w'-]+\b", clean)
    return " ".join(words[-5:]).strip() if words else ""


def build_source_rows(article_with_markers: str, anchor_map: AnchorMap, evidence_lookup: dict) -> tuple[str, list[SourceRow], list[str]]:
    contexts = marker_contexts(article_with_markers)
    cleaned = strip_markers(article_with_markers)
    visible = _normalize_visible_markdown(cleaned)
    proposed = {a.evidence_id: a.phrase.strip() for a in anchor_map.anchors}
    rows: list[SourceRow] = []
    warnings: list[str] = []
    used_urls: set[str] = set()
    n = 1

    for eid in contexts:
        pair = evidence_lookup.get(eid)
        if not pair:
            warnings.append(f"Unknown evidence marker: {eid}")
            continue
        evidence, source = pair
        if not source.url:
            # Private-only evidence remains auditable but cannot become a public hyperlink.
            continue
        if source.url in used_urls:
            continue
        phrase = proposed.get(eid, "")
        if not phrase or (phrase not in cleaned and phrase not in visible):
            phrase = _fallback_phrase(contexts[eid], evidence.entities)
        if not phrase or (phrase not in cleaned and phrase not in visible):
            warnings.append(f"Could not validate exact anchor for {eid}: {phrase!r}")
            continue
        rows.append(SourceRow(str(n), phrase, source.url, eid))
        used_urls.add(source.url)
        n += 1
    return cleaned, rows, warnings


def write_source_csv(path: Path, rows: list[SourceRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_number", "phrase", "link"])
        for row in rows:
            writer.writerow([row.source_number, row.phrase, row.link])
