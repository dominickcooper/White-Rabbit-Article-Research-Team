"""Build a read-only inventory and review packets for the Part 5 source corpus.

The script never writes inside ``sources``. Generated artifacts live beside this
script under ``research/generated`` so the corpus can be re-indexed reproducibly.
"""

from __future__ import annotations

import csv
import hashlib
import html
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


HERE = Path(__file__).resolve().parent
ARTICLE_DIR = HERE.parent
SOURCE_DIR = ARTICLE_DIR / "sources"
GENERATED_DIR = HERE / "generated"
TEXT_DIR = GENERATED_DIR / "normalized_text"
PACKET_DIR = GENERATED_DIR / "review_packets"
MAX_PACKET_CHARS = 120_000
MAX_SEGMENT_CHARS = 100_000

TERM_PATTERNS = {
    "two_fold": r"\b(?:project\s+)?two[- ]fold\b",
    "cia": r"\b(?:cia|central intelligence agency)\b",
    "federal_bureau_narcotics": r"\b(?:fbn|federal bureau of narcotics)\b",
    "bndd": r"\b(?:bndd|bureau of narcotics and dangerous drugs)\b",
    "dea": r"\b(?:dea|drug enforcement administration)\b",
    "usaid_aid": r"\b(?:usaid|u\.s\.\s+aid|agency for international development)\b",
    "ops": r"\b(?:ops|office of public safety)\b",
    "ipa": r"\b(?:ipa|international police academy)\b",
    "mkultra": r"\bmk[- ]?ultra\b",
    "internal_security": r"\binternal security\b",
    "covert": r"\bcovert\b",
    "narcotics": r"\bnarcotic(?:s)?\b",
    "intelligence": r"\bintelligence\b",
    "recruit": r"\brecruit(?:ed|ing|ment|s)?\b",
    "corson": r"\bcorson\b",
    "conein": r"\bconein\b",
    "siragusa": r"\bsiragusa\b",
    "williams": r"\bgarland\s+(?:h\.?\s+)?williams\b",
    "valentine": r"\bdouglas\s+valentine\b",
}


class VisibleHTML(HTMLParser):
    """Small dependency-free HTML-to-text extractor."""

    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl",
        "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav",
        "ol", "p", "pre", "section", "table", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif not self.hidden_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        joined = html.unescape("".join(self.parts)).replace("\xa0", " ")
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r" *\n *", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip() + "\n"


@dataclass
class Record:
    source_id: str
    relative_path: str
    extension: str
    bytes: int
    sha256: str
    normalized_sha256: str
    exact_duplicate_group: str
    normalized_duplicate_group: str
    characters: int
    words: int
    lines: int
    years: str
    term_counts: dict[str, int]
    normalized_path: str


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def visible_text(path: Path, data: bytes) -> str:
    raw = decode_bytes(data)
    if path.suffix.lower() in {".htm", ".html"}:
        parser = VisibleHTML()
        parser.feed(raw)
        parser.close()
        return parser.text()
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def normalized_for_hash(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_output_name(source_id: str, relative_path: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", relative_path).strip("._")
    return f"{source_id}_{stem[:140]}.txt"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def segment_text(text: str) -> list[tuple[int, int, str]]:
    """Split long generated copies at paragraph/newline boundaries.

    Offsets refer to the extracted text, not to byte or page positions in the source.
    """
    if len(text) <= MAX_SEGMENT_CHARS:
        return [(0, len(text), text)]
    segments: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        target = min(start + MAX_SEGMENT_CHARS, len(text))
        if target < len(text):
            break_at = text.rfind("\n\n", start + MAX_SEGMENT_CHARS // 2, target)
            if break_at < 0:
                break_at = text.rfind("\n", start + MAX_SEGMENT_CHARS // 2, target)
            if break_at > start:
                target = break_at + 1
        segments.append((start, target, text[start:target]))
        start = target
    return segments


def main() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    PACKET_DIR.mkdir(parents=True, exist_ok=True)

    paths = sorted(
        (path for path in SOURCE_DIR.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(SOURCE_DIR).as_posix().casefold(),
    )
    staged: list[dict[str, object]] = []
    for number, path in enumerate(paths, start=1):
        source_id = f"P5-{number:04d}"
        relative_path = path.relative_to(SOURCE_DIR).as_posix()
        data = path.read_bytes()
        text = visible_text(path, data)
        normalized = normalized_for_hash(text)
        normalized_name = safe_output_name(source_id, relative_path)
        normalized_path = TEXT_DIR / normalized_name
        normalized_path.write_text(text, encoding="utf-8")
        counts = {
            name: len(re.findall(pattern, text, flags=re.IGNORECASE))
            for name, pattern in TERM_PATTERNS.items()
        }
        years = sorted(set(re.findall(r"\b(?:18|19|20)\d{2}\b", text)))
        staged.append(
            {
                "source_id": source_id,
                "relative_path": relative_path,
                "extension": path.suffix.lower(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "characters": len(text),
                "words": len(re.findall(r"\b\w+\b", text, flags=re.UNICODE)),
                "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
                "years": ";".join(years),
                "term_counts": counts,
                "normalized_path": normalized_path.relative_to(HERE).as_posix(),
                "text": text,
            }
        )

    exact_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    normalized_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in staged:
        exact_groups[str(item["sha256"])].append(item)
        normalized_groups[str(item["normalized_sha256"])].append(item)
    exact_ids = {
        digest: f"EXACT-{index:03d}"
        for index, digest in enumerate(
            sorted(d for d, items in exact_groups.items() if len(items) > 1), start=1
        )
    }
    normalized_ids = {
        digest: f"NORM-{index:03d}"
        for index, digest in enumerate(
            sorted(d for d, items in normalized_groups.items() if len(items) > 1), start=1
        )
    }

    manifest_rows: list[dict[str, object]] = []
    for item in staged:
        row = {
            "source_id": item["source_id"],
            "relative_path": item["relative_path"],
            "extension": item["extension"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "normalized_sha256": item["normalized_sha256"],
            "exact_duplicate_group": exact_ids.get(str(item["sha256"]), ""),
            "normalized_duplicate_group": normalized_ids.get(str(item["normalized_sha256"]), ""),
            "characters": item["characters"],
            "words": item["words"],
            "lines": item["lines"],
            "years": item["years"],
            "normalized_path": item["normalized_path"],
        }
        row.update(item["term_counts"])
        manifest_rows.append(row)

    manifest_fields = [
        "source_id", "relative_path", "extension", "bytes", "sha256",
        "normalized_sha256", "exact_duplicate_group", "normalized_duplicate_group",
        "characters", "words", "lines", "years", "normalized_path",
        *TERM_PATTERNS.keys(),
    ]
    write_csv(GENERATED_DIR / "corpus_manifest.csv", manifest_fields, manifest_rows)

    duplicate_rows: list[dict[str, object]] = []
    for kind, groups, ids in (
        ("exact", exact_groups, exact_ids),
        ("normalized", normalized_groups, normalized_ids),
    ):
        for digest, items in groups.items():
            if len(items) < 2:
                continue
            for item in items:
                duplicate_rows.append(
                    {
                        "duplicate_type": kind,
                        "group_id": ids[digest],
                        "source_id": item["source_id"],
                        "relative_path": item["relative_path"],
                        "sha256": digest,
                    }
                )
    write_csv(
        GENERATED_DIR / "duplicate_groups.csv",
        ["duplicate_type", "group_id", "source_id", "relative_path", "sha256"],
        duplicate_rows,
    )

    review_segments: list[dict[str, object]] = []
    for item in staged:
        segments = segment_text(str(item["text"]))
        for segment_number, (start, end, segment) in enumerate(segments, start=1):
            review_segments.append(
                {
                    **item,
                    "segment_number": segment_number,
                    "segment_count": len(segments),
                    "segment_start": start,
                    "segment_end": end,
                    "segment_text": segment,
                    "segment_characters": len(segment),
                }
            )

    packets: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    current_chars = 0
    for item in review_segments:
        size = int(item["segment_characters"])
        if current and current_chars + size > MAX_PACKET_CHARS:
            packets.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += size
        if current_chars >= MAX_PACKET_CHARS:
            packets.append(current)
            current = []
            current_chars = 0
    if current:
        packets.append(current)

    packet_index_rows: list[dict[str, object]] = []
    for packet_number, packet in enumerate(packets, start=1):
        packet_name = f"batch_{packet_number:03d}.txt"
        packet_path = PACKET_DIR / packet_name
        pieces = []
        for item in packet:
            pieces.append(
                "\n".join(
                    [
                        "=" * 88,
                        f"SOURCE_ID: {item['source_id']}",
                        f"RELATIVE_PATH: {item['relative_path']}",
                        f"SHA256: {item['sha256']}",
                        f"SOURCE_CHARACTERS: {item['characters']}",
                        f"SEGMENT: {item['segment_number']}/{item['segment_count']}",
                        f"EXTRACTED_CHARACTER_OFFSETS: {item['segment_start']}:{item['segment_end']}",
                        "=" * 88,
                        str(item["segment_text"]),
                    ]
                )
            )
            packet_index_rows.append(
                {
                    "batch": packet_number,
                    "packet_path": packet_path.relative_to(HERE).as_posix(),
                    "source_id": item["source_id"],
                    "relative_path": item["relative_path"],
                    "segment_number": item["segment_number"],
                    "segment_count": item["segment_count"],
                    "segment_start": item["segment_start"],
                    "segment_end": item["segment_end"],
                    "characters": item["segment_characters"],
                }
            )
        packet_path.write_text("\n\n".join(pieces), encoding="utf-8")
    write_csv(
        GENERATED_DIR / "review_batch_index.csv",
        [
            "batch", "packet_path", "source_id", "relative_path", "segment_number",
            "segment_count", "segment_start", "segment_end", "characters",
        ],
        packet_index_rows,
    )

    review_ledger = HERE / "CORPUS_REVIEW_LEDGER.csv"
    if not review_ledger.exists():
        review_rows = [
            {
                "source_id": item["source_id"],
                "relative_path": item["relative_path"],
                "review_status": "UNREVIEWED",
                "reviewed_on": "",
                "relevance": "",
                "document_type": "",
                "date": "",
                "author_sender": "",
                "recipient": "",
                "primary_secondary": "",
                "key_people": "",
                "key_organizations": "",
                "key_findings": "",
                "limitations_ocr": "",
                "follow_up": "",
            }
            for item in staged
        ]
        write_csv(
            review_ledger,
            [
                "source_id", "relative_path", "review_status", "reviewed_on",
                "relevance", "document_type", "date", "author_sender", "recipient",
                "primary_secondary", "key_people", "key_organizations", "key_findings",
                "limitations_ocr", "follow_up",
            ],
            review_rows,
        )

    summary = Counter()
    summary["files"] = len(staged)
    summary["source_bytes"] = sum(int(item["bytes"]) for item in staged)
    summary["extracted_characters"] = sum(int(item["characters"]) for item in staged)
    summary["extracted_words"] = sum(int(item["words"]) for item in staged)
    summary["exact_duplicate_groups"] = len(exact_ids)
    summary["normalized_duplicate_groups"] = len(normalized_ids)
    summary["review_batches"] = len(packets)
    summary_lines = ["# Corpus index summary", ""]
    summary_lines.extend(f"- {key.replace('_', ' ').title()}: {value:,}" for key, value in summary.items())
    summary_lines.extend(["", "## Term totals", ""])
    for name in TERM_PATTERNS:
        total = sum(int(item["term_counts"][name]) for item in staged)
        summary_lines.append(f"- {name}: {total:,}")
    (GENERATED_DIR / "INDEX_SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
