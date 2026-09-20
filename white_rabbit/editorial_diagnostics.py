"""Non-blocking editorial diagnostics for near-final White Rabbit Markdown.

These checks expose patterns for human review. They are deliberately not a style
score and never decide whether a supported claim is true.
"""
from __future__ import annotations

from collections import Counter
import math
import re


REVIEW_STEMS = (
    "that matters", "this matters", "seen in that context", "in other words",
    "the pattern", "taken together", "the better conclusion", "the harder question",
    "the answer cannot", "this gives us", "that distinction", "the directive",
)

PERFORMATIVE_CAUTION_STEMS = (
    "i can't prove", "i cannot prove", "i am not going to", "i won't",
    "the most defensible", "what the document proves", "what the page proves",
    "what the record proves", "the evidence allows", "the evidence supports",
    "it would be irresponsible", "we should be careful", "important distinction",
    "that distinction matters", "the file needs a warning label", "to be precise",
)

CAUTION_SENTENCE = re.compile(
    r"\b(?:i (?:can't|cannot|won't|will not|am not going to)|we should be careful|"
    r"it would be irresponsible|the most defensible|what (?:the )?(?:document|page|"
    r"record|evidence) proves|the (?:available )?evidence (?:allows|supports|does not "
    r"allow)|(?:the )?records? (?:do not|don't) (?:prove|establish|show)|(?:does|do) "
    r"not (?:prove|establish|show|permit)|important distinction|that (?:limit|"
    r"distinction) matters|to be precise)\b",
    re.I,
)


def _plain(text: str) -> str:
    text = re.sub(r"(?ms)^(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*(?:\n|$)", "", text)
    text = re.sub(r"\[IMAGE:.*?\]", "", text)
    text = re.sub(r"\[([^\]]+)\]\((?:https?://)[^\s()]+\)", r"\1", text)
    return re.sub(r"[*_`]", "", text)


def _paragraphs(text: str) -> list[str]:
    blocks = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", _plain(text))]
    return [p for p in blocks if p and not p.startswith(("#", "|", "[[", "[IMAGE:"))]


def _variation(values: list[int]) -> float | None:
    if len(values) < 2 or not sum(values):
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) / mean


def _caution_density(paragraphs: list[str]) -> tuple[int, int]:
    """Count caution sentences and compact passages with stacked limitations.

    This is deliberately only a lexical prompt for editorial review. It does not decide
    whether a qualification is necessary or whether a claim is supported.
    """
    caution_sentences = 0
    dense_passages = 0
    for paragraph in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
        marked = sum(bool(CAUTION_SENTENCE.search(sentence)) for sentence in sentences)
        caution_sentences += marked
        if len(sentences) >= 3 and marked >= 2 and sum(len(s.split()) for s in sentences) <= 120:
            dense_passages += 1
    return caution_sentences, dense_passages


def analyze_editorial_style(article: str) -> dict:
    """Return diagnostic metrics and advisory warnings for publication Markdown."""
    paragraphs = _paragraphs(article)
    word_counts = [len(re.findall(r"\b[\w’'-]+\b", p)) for p in paragraphs]
    starts = Counter()
    for paragraph in paragraphs:
        words = re.findall(r"[A-Za-z’']+", paragraph.lower())
        if words:
            starts[" ".join(words[: min(2, len(words))])] += 1

    lower = _plain(article).lower()
    stem_counts = {stem: len(re.findall(r"\b" + re.escape(stem) + r"\b", lower)) for stem in REVIEW_STEMS}
    stem_counts = {stem: count for stem, count in stem_counts.items() if count}
    performative_caution = {
        stem: len(re.findall(r"\b" + re.escape(stem) + r"\b", lower))
        for stem in PERFORMATIVE_CAUTION_STEMS
    }
    performative_caution = {stem: count for stem, count in performative_caution.items() if count}
    caution_sentences, caution_density_passages = _caution_density(paragraphs)
    symmetric_contrasts = len(re.findall(
        r"\b(?:not (?:merely|just|only)?\b[^.!?;]{0,90}\bbut\b|both\b[^.!?;]{0,90}\band\b|"
        r"it would be (?:an equal )?mistake\b)", lower
    ))

    bold_spans = re.findall(r"(?<!\*)\*\*(?!\*)(.+?)(?<!\*)\*\*(?!\*)", article, re.S)
    bold_italic_spans = re.findall(r"\*\*\*(.+?)\*\*\*", article, re.S)
    italic_spans = re.findall(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", article, re.S)
    prose_chars = max(1, len(re.sub(r"\s+", "", _plain(article))))
    bold_chars = sum(len(_plain(x)) for x in bold_spans + bold_italic_spans)
    italic_chars = sum(len(_plain(x)) for x in italic_spans + bold_italic_spans)
    repeated_bold = {k: v for k, v in Counter(_plain(x).casefold().strip() for x in bold_spans).items()
                     if k and v >= 3}
    fully_bold = [p for p in re.split(r"\n\s*\n", article)
                  if re.fullmatch(r"\s*\*\*[^*].*?\*\*\s*", p, re.S)]
    isolated = sum(1 for count in word_counts if 0 < count <= 10)

    list_lines = re.findall(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+\S", article)
    list_groups = len(re.findall(r"(?m)(?:^\s*(?:[-+*]|\d+[.)])\s+.+\n?){2,}", article))
    images = re.findall(r"\[IMAGE:\s*([^|\]\n]+)\|\s*ALT:\s*([^\]\n]+)\]", article)
    image_descriptions = Counter(re.sub(r"\s+", " ", d).strip().casefold() for d, _ in images)

    warnings: list[str] = []
    repeated_starts = {s: c for s, c in starts.items() if c >= 3 and s.split()[0] in {"this", "that", "the", "it"}}
    if repeated_starts:
        warnings.append("STYLE repeated paragraph openings: " + ", ".join(f"{s!r} ×{c}" for s, c in sorted(repeated_starts.items())))
    if sum(stem_counts.values()) >= 3:
        warnings.append("STYLE cumulative explanatory scaffold: " + ", ".join(f"{s!r} ×{c}" for s, c in stem_counts.items()))
    if sum(performative_caution.values()) >= 2:
        warnings.append("STYLE Type-B performative caution: " + ", ".join(
            f"{s!r} ×{c}" for s, c in performative_caution.items()
        ) + "; review for a shorter factual qualifier.")
    if caution_density_passages:
        warnings.append(
            f"STYLE caution density in {caution_density_passages} passage(s); review for "
            "FACT -> LIMIT -> INFERENCE -> MOVE."
        )
    if symmetric_contrasts >= 3:
        warnings.append(f"STYLE {symmetric_contrasts} symmetric contrast constructions; keep only those doing real analytical work.")
    variation = _variation(word_counts)
    if variation is not None and len(word_counts) >= 8 and variation < 0.35:
        warnings.append("STYLE paragraph lengths are unusually uniform; review rhythm without manufacturing fragments.")
    if fully_bold:
        warnings.append(f"FORMATTING {len(fully_bold)} paragraph(s) are entirely bold; confirm each is an intentional punch line.")
    if bold_chars / prose_chars > 0.22:
        warnings.append("FORMATTING bold exceeds 22% of prose characters; confirm a skimming reader still sees hierarchy.")
    if italic_chars / prose_chars > 0.14:
        warnings.append("FORMATTING italics exceed 14% of prose characters; reserve them for audible authorial voice.")
    if repeated_bold:
        warnings.append("FORMATTING repeated bold emphasis: " + ", ".join(f"{p!r} ×{c}" for p, c in repeated_bold.items()))
    if len(paragraphs) >= 20 and isolated > max(10, len(paragraphs) // 4):
        warnings.append(f"FORMATTING {isolated} short isolated paragraphs; confirm the punch-line effect has not become a metronome.")
    if list_groups >= 3 and len(list_lines) >= 15:
        warnings.append(f"LISTS {list_groups} list groups / {len(list_lines)} items; confirm relationships have not been flattened into enumeration.")
    duplicates = [d for d, c in image_descriptions.items() if c > 1]
    if duplicates:
        warnings.append("VISUAL repeated image descriptions may be redundant: " + "; ".join(duplicates))
    for description, alt in images:
        if re.search(r"\b(?:proof|proves|exposes|shows that .* secretly)\b", alt, re.I):
            warnings.append(f"VISUAL alt text appears argumentative rather than descriptive: {alt.strip()}")
        if re.search(r"\b(?:ai[- ]generated|generated art)\b", description, re.I) and re.search(
                r"\b(?:document|memo|record|file|excerpt|clipping)\b", description, re.I):
            warnings.append(f"VISUAL generated art may be substituting for documentary evidence: {description.strip()}")

    return {
        "paragraphs": len(paragraphs),
        "paragraph_length_cv": round(variation, 3) if variation is not None else None,
        "short_paragraphs": isolated,
        "rhetorical_questions": len(re.findall(r"\?", _plain(article))),
        "first_person_occurrences": len(re.findall(r"\b(?:I|me|my|we|our|us)\b", _plain(article))),
        "symmetric_contrasts": symmetric_contrasts,
        "review_stems": stem_counts,
        "performative_caution": performative_caution,
        "caution_sentences": caution_sentences,
        "caution_density_passages": caution_density_passages,
        "bold_spans": len(bold_spans),
        "italic_spans": len(italic_spans),
        "bold_italic_spans": len(bold_italic_spans),
        "list_groups": list_groups,
        "list_items": len(list_lines),
        "image_markers": len(images),
        "warnings": warnings,
    }
