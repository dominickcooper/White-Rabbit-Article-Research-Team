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
    "at minimum", "this does not prove", "the record does not show",
    "there is no evidence that", "this matters because",
)

PERFORMATIVE_CAUTION_STEMS = (
    "i can't prove", "i cannot prove", "i am not going to", "i won't",
    "the most defensible", "what the document proves", "what the page proves",
    "what the record proves", "the evidence allows", "the evidence supports",
    "it would be irresponsible", "we should be careful", "important distinction",
    "that distinction matters", "the file needs a warning label", "to be precise",
)

AI_TIC_PATTERNS = (
    ("not X but Y", r"\bnot\b[^.!?\n]{0,100}\bbut\b",
     "Delete the defensive contrast or state the affirmative finding directly."),
    ("this does not prove", r"\bthis does not prove\b",
     "Keep only a story-changing boundary; otherwise move to the implication."),
    ("that does not mean", r"\bthat does not mean\b",
     "Replace with the exact material limit, once, if it changes meaning."),
    ("that distinction matters", r"\bthat distinction matters\b",
     "Show the consequence of the distinction instead of announcing it."),
    ("the stronger conclusion", r"\bthe stronger conclusion\b",
     "State the supported conclusion directly."),
    ("the better question", r"\bthe better question\b",
     "Ask the investigative question directly or move to the next receipt."),
    ("the evidence stops short", r"\bthe evidence stops short\b",
     "Name the precise missing fact only when it changes the story."),
    ("what this actually shows", r"\bwhat this actually shows\b",
     "State what the receipt shows without a corrective preamble."),
    ("the reality is more complicated", r"\bthe reality is more complicated\b",
     "Replace the generic complication cue with the concrete conflict."),
    ("both things can be true", r"\bboth things can be true\b",
     "State the two supported facts and their relationship directly."),
    ("it is important to note", r"\bit is important to note\b",
     "Delete the announcement and state the point."),
    ("in other words", r"\bin other words\b",
     "Delete a redundant restatement or use a concrete transition."),
    ("however corrective pivot", r"\bhowever\b",
     "Keep only pivots that introduce material contrary evidence."),
    ("three-part antithesis", r"\bnot\b[^.!?\n]{0,80}[.!?]\s*not\b[^.!?\n]{0,80}[.!?]\s*(?:rather|instead)\b",
     "State the affirmative conclusion without a three-beat defensive setup."),
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


def _ai_tic_report(text: str) -> list[dict]:
    """Locate recurring rhetorical constructions for editorial judgment.

    Necessity cannot be inferred lexically, so the report explicitly requires an editor's
    decision instead of pretending a count can decide whether a boundary belongs.
    """
    plain = _plain(text)
    findings = []
    for phrase, pattern, recommendation in AI_TIC_PATTERNS:
        matches = list(re.finditer(pattern, plain, re.I | re.S))
        if not matches:
            continue
        findings.append({
            "phrase": phrase,
            "count": len(matches),
            "locations": [f"line {plain.count(chr(10), 0, match.start()) + 1}" for match in matches],
            "necessary": "EDITORIAL REVIEW REQUIRED",
            "recommended_action": recommendation,
        })
    return findings


def _located_blocks(text: str) -> list[dict]:
    """Return prose/heading blocks with source line numbers for rhetorical diagnostics."""
    cleaned = re.sub(r"(?ms)^(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*(?:\n|$)", "", text)
    records = []
    for match in re.finditer(r"(?ms)(?:^|\n\s*\n)(\s*\S.*?)(?=\n\s*\n|\Z)", cleaned):
        block = re.sub(r"\s+", " ", match.group(1)).strip()
        if not block or block.startswith(("|", "[[", "[IMAGE:")):
            continue
        records.append({
            "text": re.sub(r"\[([^\]]+)\]\((?:https?://)[^\s()]+\)", r"\1", block),
            "raw": block,
            "line": cleaned.count("\n", 0, match.start(1)) + 1,
        })
    return records


def _semantic_rhetoric_report(text: str, *, one_sentence_ratio: float, short_ratio: float) -> list[dict]:
    """Detect multi-paragraph rhetorical behavior as review leads.

    These are deliberately explainable heuristics. They locate sequences for the
    independent semantic editor; they never decide whether the evidence is true or a
    qualification is necessary.
    """
    blocks = _located_blocks(text)
    findings: list[dict] = []
    trigger = re.compile(
        r"\b(?:theor(?:y|ies)|testimon|account|alleg|claim|plot|network|mechanism|"
        r"overlap|connection|provocative|supplied books?)\b", re.I
    )
    boundary = re.compile(
        r"\b(?:not enough|does not have|do not have|no (?:recovered|authenticated|"
        r"financial|contemporaneous|direct)|missing (?:bridge|link|record)|fails?|"
        r"unsupported|cannot (?:prove|establish)|contested|never repaired)\b", re.I
    )
    redirect = re.compile(
        r"\b(?:something else survives|more important|what we can actually prove|"
        r"cover-up we can .*prove|safer conclusion|instead,? the (?:real|documented)|"
        r"the real discovery)\b", re.I
    )

    sequence_seen = False
    for start in range(len(blocks)):
        window = blocks[start:start + 10]
        if not window or not trigger.search(window[0]["text"]):
            continue
        boundary_rows = [row for row in window[1:] if boundary.search(row["text"])]
        redirect_row = next((row for row in window[1:] if redirect.search(row["text"])), None)
        if len(boundary_rows) >= 2 and redirect_row:
            excerpt = " ".join(row["text"] for row in window[:window.index(redirect_row) + 1])[:700]
            locator = f"lines {window[0]['line']}–{redirect_row['line']}"
            findings.extend([
                {
                    "category": "DEFENSIVE SEQUENCE",
                    "locator": locator,
                    "excerpt": excerpt,
                    "recommended_fix": "Develop the source-selected branch before adjudicating it; keep one material boundary and do not redirect to a safer substitute story without author approval.",
                    "basis": "heuristic multi-paragraph sequence; semantic editor must confirm",
                },
                {
                    "category": "CONTRIVED DIALECTIC",
                    "locator": locator,
                    "excerpt": excerpt,
                    "recommended_fix": "Replace the staged allegation/negation/safer-answer dialectic with the actual discovery sequence and cumulative evidence.",
                    "basis": "heuristic multi-paragraph sequence; semantic editor must confirm",
                },
                {
                    "category": "PREMATURE ADJUDICATION",
                    "locator": locator,
                    "excerpt": excerpt,
                    "recommended_fix": "Check the rabbit-hole pursuit record; add missing people, documents, logistics and next-hop findings before closing the branch.",
                    "basis": "heuristic proximity between introduction and rejection",
                },
            ])
            sequence_seen = True
            break

    for start in range(max(0, len(blocks) - 5)):
        window = blocks[start:start + 6]
        marked = [row for row in window if boundary.search(row["text"])]
        if len(marked) >= 3:
            findings.append({
                "category": "NARRATIVE STAGNATION",
                "locator": f"lines {window[0]['line']}–{window[-1]['line']}",
                "excerpt": " ".join(row["text"] for row in window)[:700],
                "recommended_fix": "Compress repeated evidentiary boundaries and move to the next receipt, connection, or unresolved search target.",
                "basis": "three or more limiting moves in a six-block window",
            })
            break

    plain = _plain(text)
    audit_terms = len(re.findall(
        r"\b(?:prove|proven|evidence|authenticated|unsupported|decisive bridge|"
        r"payment trail|operational record|maximum thesis|conclusion)\b", plain, re.I
    ))
    if audit_terms >= 8 and sequence_seen:
        findings.append({
            "category": "AUDITOR VOICE",
            "locator": "article-wide, concentrated in the defensive sequence",
            "excerpt": "Multiple proof-status and adjudication terms dominate the narrative turn.",
            "recommended_fix": "Move proof-status bookkeeping to the audit; let publication prose show the receipts, name one boundary, and continue the investigation.",
            "basis": f"{audit_terms} audit-language signals plus a defensive sequence",
        })

    if re.search(r"\b(?:maximum|central|original) thesis fails?\b", plain, re.I) and redirect.search(plain):
        match = re.search(r"\b(?:maximum|central|original) thesis fails?\b", plain, re.I)
        findings.append({
            "category": "THESIS SUBSTITUTION",
            "locator": f"line {plain.count(chr(10), 0, match.start()) + 1}" if match else "article",
            "excerpt": plain[match.start():match.start() + 500] if match else "",
            "recommended_fix": "Compare against SOURCE_THESIS.md and the author-decision field. A fundamentally different article requires AUTHOR THESIS DECISION REQUIRED.",
            "basis": "explicit thesis failure followed by a safer-story redirect",
        })

    for row in blocks:
        if "thewhiterabbitreport" in row["raw"].casefold() and re.search(
                r"\b(?:not a continuation|callback .* not a claim|not evidence of|analogy only)\b",
                row["text"], re.I):
            findings.append({
                "category": "CANON DEFENSIVENESS",
                "locator": f"line {row['line']}",
                "excerpt": row["text"][:500],
                "recommended_fix": "Use the established canon premise to open the new edge; keep a boundary only when new contradictory evidence makes it material.",
                "basis": "canon callback immediately re-litigated or neutralized",
            })
            break

    narrative_blocks = [row for row in blocks if not row["text"].startswith("#")]
    first_person = len(re.findall(r"\b(?:I|me|my|we|our|us)\b", plain))
    if len(narrative_blocks) >= 35 and first_person <= 1:
        findings.append({
            "category": "NARRATOR ABSENCE",
            "locator": "article-wide",
            "excerpt": f"{first_person} first-person signal across {len(narrative_blocks)} narrative blocks.",
            "recommended_fix": "Compare with Gold prose and add only genuine investigative observation, curiosity, theory, or reaction—never quota-driven first person.",
            "basis": "diagnostic signal, not a narrator quota",
        })

    if len(narrative_blocks) >= 20 and one_sentence_ratio > 0.45 and short_ratio > 0.25:
        findings.append({
            "category": "MECHANICAL REVEAL WRITING",
            "locator": "article-wide",
            "excerpt": f"One-sentence ratio {one_sentence_ratio:.2f}; short-paragraph ratio {short_ratio:.2f}.",
            "recommended_fix": "Compare the actual paragraph distribution with relevant Gold articles and merge manufactured suspense beats while preserving earned punches.",
            "basis": "combined rhythm diagnostics; no numeric literary verdict",
        })
    return findings


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
    ai_tics = _ai_tic_report(article)
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
    sentence_counts = [len([s for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]) for p in paragraphs]
    one_sentence = sum(count == 1 for count in sentence_counts)
    abstract_blocks = 0
    for paragraph in paragraphs:
        if len(paragraph.split()) >= 90 and not re.search(
                r"\b(?:memo|letter|report|document|record|email|interview|court|contract|"
                r"investigator|witness|officer|agent|director|president|professor|banker|"
                r"said|told|wrote|found|arrived|met|paid|hired|sent|visited|19\d\d|20\d\d)\b",
                paragraph, re.I):
            abstract_blocks += 1

    list_lines = re.findall(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+\S", article)
    list_groups = len(re.findall(r"(?m)(?:^\s*(?:[-+*]|\d+[.)])\s+.+\n?){2,}", article))
    images = re.findall(r"\[IMAGE:\s*([^|\]\n]+)\|\s*ALT:\s*([^\]\n]+)\]", article)
    image_descriptions = Counter(re.sub(r"\s+", " ", d).strip().casefold() for d, _ in images)

    one_sentence_ratio = one_sentence / max(1, len(paragraphs))
    short_ratio = isolated / max(1, len(paragraphs))
    semantic_rhetoric = _semantic_rhetoric_report(
        article, one_sentence_ratio=one_sentence_ratio, short_ratio=short_ratio
    )

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
    repeated_ai_tics = [item for item in ai_tics if item["count"] >= 2]
    if repeated_ai_tics:
        warnings.append("STYLE repeated AI-tic constructions: " + ", ".join(
            f"{item['phrase']!r} ×{item['count']} at {', '.join(item['locations'])}"
            for item in repeated_ai_tics
        ) + "; decide necessity and delete or rewrite locally without substituting a new formula.")
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
    if len(paragraphs) >= 12 and one_sentence > len(paragraphs) * 0.45:
        warnings.append(f"STYLE {one_sentence}/{len(paragraphs)} prose paragraphs contain one sentence; use one-line paragraphs selectively.")
    caveat_total = sum(performative_caution.values()) + caution_sentences
    if len(paragraphs) >= 10 and caveat_total > max(6, len(paragraphs) // 3):
        warnings.append(f"STYLE unusually high caveat density ({caveat_total} signals); verify attribution can carry some qualification.")
    if abstract_blocks:
        warnings.append(f"STYLE {abstract_blocks} long abstract block(s) contain no obvious person, document, event, action or date.")
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

    if semantic_rhetoric:
        categories = ", ".join(dict.fromkeys(item["category"] for item in semantic_rhetoric))
        warnings.append(
            "SEMANTIC REVIEW REQUIRED for located rhetorical patterns: " + categories +
            ". Heuristics locate passages; the independent editor decides and records the repair."
        )

    return {
        "paragraphs": len(paragraphs),
        "paragraph_length_cv": round(variation, 3) if variation is not None else None,
        "short_paragraphs": isolated,
        "one_sentence_paragraphs": one_sentence,
        "abstract_blocks": abstract_blocks,
        "rhetorical_questions": len(re.findall(r"\?", _plain(article))),
        "first_person_occurrences": len(re.findall(r"\b(?:I|me|my|we|our|us)\b", _plain(article))),
        "symmetric_contrasts": symmetric_contrasts,
        "review_stems": stem_counts,
        "performative_caution": performative_caution,
        "caution_sentences": caution_sentences,
        "caution_density_passages": caution_density_passages,
        "ai_tics": ai_tics,
        "semantic_rhetoric": semantic_rhetoric,
        "bold_spans": len(bold_spans),
        "italic_spans": len(italic_spans),
        "bold_italic_spans": len(bold_italic_spans),
        "list_groups": list_groups,
        "list_items": len(list_lines),
        "image_markers": len(images),
        "warnings": warnings,
    }
