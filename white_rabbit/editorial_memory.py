"""Durable editorial memory and human-approved post-publication learning."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import shutil
import statistics
from urllib.parse import urlparse

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

MEMORY_FILES = ("VOICE_CANON.md", "ANTI_PATTERNS.md", "EDITORIAL_LESSONS.md", "GOLD_ARTICLES.json")
PROJECT_TEMPLATES = {
    "research/SOURCE_THESIS.md": "SOURCE_THESIS_TEMPLATE.md",
    "research/STYLE_PROFILE.md": "STYLE_PROFILE_TEMPLATE.md",
    "research/ENTITY_NETWORK.md": "ENTITY_NETWORK_TEMPLATE.md",
    "research/RABBIT_HOLE_QUEUE.md": "RABBIT_HOLE_QUEUE_TEMPLATE.md",
    "research/CONNECTION_REPORT.md": "CONNECTION_REPORT_TEMPLATE.md",
    "research/CONNECTION_CHAINS.md": "CONNECTION_CHAINS_TEMPLATE.md",
    "research/BOOK_LEADS.md": "BOOK_LEADS_TEMPLATE.md",
    "research/BIBLIOGRAPHY_TRACE.csv": "BIBLIOGRAPHY_TRACE_TEMPLATE.csv",
    "research/STORY_DECISION.md": "STORY_DECISION_TEMPLATE.md",
    "research/STORY_SPINE.md": "STORY_SPINE_TEMPLATE.md",
    "research/WRITER_PACKET.md": "WRITER_PACKET_TEMPLATE.md",
    "research/SEMANTIC_EDITORIAL_REVIEW.md": "SEMANTIC_EDITORIAL_REVIEW_TEMPLATE.md",
    "research/QUALITY_GATES.md": "QUALITY_GATES_TEMPLATE.md",
    "output/editorial_audit.md": "EDITORIAL_AUDIT_TEMPLATE.md",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_dir(root: Path) -> Path:
    cfg = json.loads((root / "white_rabbit_codex_config.json").read_text(encoding="utf-8"))
    relative = cfg.get("editorial_memory_dir", "research_library/editorial_memory")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise ValueError("editorial_memory_dir must remain inside the repository")
    return target


def initialize(root: Path) -> Path:
    target = memory_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    (target / "revision_history").mkdir(exist_ok=True)
    (target / "pending_learnings").mkdir(exist_ok=True)
    seeds = root / "templates/editorial_memory"
    for name in MEMORY_FILES:
        destination = target / name
        if not destination.exists():
            source = seeds / name
            if not source.is_file():
                source = PACKAGE_ROOT / "templates/editorial_memory" / name
            shutil.copyfile(source, destination)
    return target


def ensure_project_artifacts(root: Path, project: Path) -> list[Path]:
    """Add only absent workflow artifacts; never replace project work."""
    initialize(root)
    created = []
    for relative, template in PROJECT_TEMPLATES.items():
        path = project / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "templates" / template
            if not source.is_file():
                source = PACKAGE_ROOT / "templates" / template
            shutil.copyfile(source, path)
            created.append(path)
    return created


def load_gold_articles(root: Path, *, include_missing: bool = False) -> list[dict]:
    registry = initialize(root) / "GOLD_ARTICLES.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("GOLD_ARTICLES.json must contain a JSON list")
    result = []
    for index, entry in enumerate(data, 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError(f"Invalid Gold article entry {index}")
        path = (root / entry["path"]).resolve()
        safe = path.is_relative_to(root.resolve()) and path != root.resolve()
        item = {**entry, "exists": safe and path.is_file()}
        if entry.get("approved") is True and (item["exists"] or include_missing):
            result.append(item)
    return result


def select_gold_articles(root: Path, query: str, limit: int = 4) -> list[dict]:
    words = set(re.findall(r"[a-z0-9]+", query.casefold()))
    ranked = []
    for entry in load_gold_articles(root):
        haystack = " ".join([entry.get("title", ""), entry.get("notes", ""), *entry.get("tags", [])]).casefold()
        score = sum(word in haystack for word in words)
        ranked.append((score, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].get("title", "")))
    return [entry for _, entry in ranked[: max(0, min(limit, 4))]]


def revision_key(project: Path, *, series_slug: str | None = None) -> str:
    return f"{series_slug}__{project.name}" if series_slug else project.name


def preserve_pre_human_snapshot(root: Path, project: Path, *, series_slug: str | None = None) -> Path | None:
    article = project / "output/article.md"
    if not article.is_file() or not article.read_text(encoding="utf-8-sig").strip():
        return None
    folder = initialize(root) / "revision_history" / revision_key(project, series_slug=series_slug)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / "draft_before_human_edit.md"
    if not snapshot.exists():
        shutil.copyfile(article, snapshot)
    metadata = folder / "metadata.json"
    if not metadata.exists():
        metadata.write_text(json.dumps({"project": project.name, "series": series_slug,
                                        "snapshot_created_at": _now()}, indent=2) + "\n", encoding="utf-8")
    return snapshot


CATEGORIES = {
    "RESEARCH_DISCOVERY", "CONNECTION_ADDED", "PERSONNEL_RABBIT_HOLE", "STRUCTURE",
    "REVEAL_ORDER", "VOICE", "CAVEAT_REMOVAL", "CAVEAT_ADDITION", "SOURCE_TREATMENT",
    "STRONGER_INFERENCE", "WEAKER_INFERENCE", "FRAMING_CHANGE", "SERIES_CALLBACK",
    "COMPRESSION", "EXPANSION", "EXPLANATION", "CONCLUSION", "FACTUAL_CORRECTION",
    "SEO", "FORMATTING",
}
SCOPES = {"global", "investigative", "series", "article-specific"}
CONFIDENCE = {"high", "medium", "low"}
STATUSES = {"pending", "approved", "rejected", "promoted"}
COMPARISON_MODES = {"editorial_revision", "story_replacement"}
REVISION_KEY_PATTERN = re.compile(r"[a-z0-9-]+(?:__[a-z0-9-]+)*")

_IDENTITY_STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "an", "and", "are", "as", "at",
    "be", "because", "been", "before", "between", "but", "by", "can", "could", "did",
    "do", "does", "for", "from", "had", "has", "have", "he", "her", "here", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "more", "most", "not", "of",
    "on", "one", "or", "our", "part", "said", "she", "so", "some", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "through", "to",
    "two", "up", "usaid", "cia", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "why", "will", "with", "would", "you",
}


def _blocks(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n\s*\n", text)
            if block.strip() and not block.lstrip().startswith("[[")]


def _prose_blocks(text: str) -> list[str]:
    return [block for block in _blocks(text) if not block.startswith(("#", "[IMAGE:", "|", "- "))]


def _narrative_prose(text: str) -> list[str]:
    narrative = re.split(r"(?im)^##\s+(?:FAQS?|FREQUENTLY ASKED QUESTIONS|YOU MAY BE INTERESTED)", text, maxsplit=1)[0]
    return _prose_blocks(narrative)


def _headings(text: str) -> list[str]:
    return [match.group(2).strip() for match in re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text)]


def _links(text: str) -> dict[str, str]:
    return {url: label for label, url in re.findall(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", text)}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", re.sub(r"\[[^]]+\]\([^)]+\)", "", text)))


def _paragraph_metrics(text: str) -> dict:
    from .editorial_diagnostics import analyze_editorial_style
    paragraphs = _prose_blocks(text)
    lengths = [_word_count(p) for p in paragraphs]
    diagnostics = analyze_editorial_style(text)
    return {
        "paragraphs": len(paragraphs),
        "average_words": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "median_words": round(statistics.median(lengths), 1) if lengths else 0,
        "one_sentence_paragraphs": diagnostics["one_sentence_paragraphs"],
        "rhetorical_questions": diagnostics["rhetorical_questions"],
        "first_person_occurrences": diagnostics["first_person_occurrences"],
        "list_groups": diagnostics["list_groups"],
        "list_items": diagnostics["list_items"],
        "caution_sentences": diagnostics["caution_sentences"],
        "anti_pattern_occurrences": diagnostics["review_stems"],
    }


def _entities(text: str) -> dict[str, int]:
    plain = re.sub(r"\[[^]]+\]\([^)]+\)", "", text)
    candidates = re.findall(r"\b(?:[A-Z][A-Za-z’'-]+(?:\s+(?:[A-Z][A-Za-z’'-]+|of|the|and)){1,4}|[A-Z]{2,8})\b", plain)
    stop = {"The", "This", "That", "White Rabbit", "FAQ", "IMAGE", "ALT", "SUBSCRIBE", "SHARE"}
    counts: dict[str, int] = {}
    for name in candidates:
        name = re.sub(r"\s+", " ", name).strip()
        if name not in stop and len(name) >= 3:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _qualification_sentences(text: str) -> list[str]:
    pattern = re.compile(
        r"\b(?:does not prove|do not prove|no (?:primary )?evidence|record does not|records do not|"
        r"cannot establish|unconfirmed|uncorroborated|according to|told|recalled|alleged|"
        r"uncertain|unclear|disputed|not established|not documented|at minimum)\b", re.I)
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    return [sentence.strip()[:700] for sentence in sentences if pattern.search(sentence)][:20]


def _format_excerpt(block: str, limit: int = 900) -> str:
    return block[:limit] + ("…" if len(block) > limit else "")


def _identity_words(text: str) -> list[str]:
    plain = re.sub(r"https?://\S+|\[[^]]+\]\([^)]+\)|[^a-zA-Z0-9’'-]+", " ", text).casefold()
    return [word.strip("’-'") for word in plain.split()
            if len(word.strip("’-'") ) >= 3 and word.strip("’-'") not in _IDENTITY_STOPWORDS]


def _title(text: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return match.group(1).strip() if match else ""


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _topical_terms(text: str, limit: int = 45) -> set[str]:
    counts = Counter(_identity_words(re.sub(r"(?m)^#{1,6}\s+.*$", "", text)))
    return {word for word, _ in counts.most_common(limit)}


def _heading_terms(text: str) -> set[str]:
    return set(_identity_words(" ".join(_headings(text))))


def _principal_entities(text: str, limit: int = 35) -> set[str]:
    ranked = sorted(_entities(text).items(), key=lambda item: (-item[1], item[0]))[:limit]
    terms: set[str] = set()
    for entity, _ in ranked:
        normalized = " ".join(_identity_words(entity))
        if normalized:
            terms.add(normalized)
            terms.update(normalized.split())
    return terms


def _source_families(text: str) -> tuple[set[str], set[str]]:
    urls = set(_links(text))
    domains = {urlparse(url).netloc.casefold().removeprefix("www.") for url in urls}
    return urls, {domain for domain in domains if domain}


def _substantial_overlap(before: str, after: str) -> float:
    old_words, new_words = _identity_words(before), _identity_words(after)
    if not old_words or not new_words:
        return 0.0
    old_shingles = {" ".join(old_words[index:index + 5]) for index in range(max(0, len(old_words) - 4))}
    new_shingles = {" ".join(new_words[index:index + 5]) for index in range(max(0, len(new_words) - 4))}
    shingle_overlap = _jaccard(old_shingles, new_shingles)
    sequence_overlap = SequenceMatcher(None, old_words, new_words, autojunk=True).ratio()
    return (0.55 * sequence_overlap) + (0.45 * shingle_overlap)


def assess_article_identity(before: str, after: str) -> dict:
    """Estimate whether two substantial articles are revisions of the same story.

    This is deliberately a multi-signal guard, not a plagiarism threshold. A thesis may
    mutate and the prose may be rewritten while title anchors, entities, topics, sources,
    or retained passages continue to identify the underlying investigation.
    """
    old_title, new_title = _title(before), _title(after)
    old_title_terms, new_title_terms = set(_identity_words(old_title)), set(_identity_words(new_title))
    old_urls, old_domains = _source_families(before)
    new_urls, new_domains = _source_families(after)
    signals = {
        "title": _jaccard(old_title_terms, new_title_terms),
        "headings": _jaccard(_heading_terms(before), _heading_terms(after)),
        "principal_entities": _jaccard(_principal_entities(before), _principal_entities(after)),
        "topic_keywords": _jaccard(_topical_terms(before), _topical_terms(after)),
        "source_families": max(_jaccard(old_urls, new_urls), _jaccard(old_domains, new_domains)),
        "substantial_text_overlap": _substantial_overlap(before, after),
    }
    weights = {
        "title": 0.25,
        "headings": 0.10,
        "principal_entities": 0.20,
        "topic_keywords": 0.20,
        "source_families": 0.10,
        "substantial_text_overlap": 0.15,
    }
    score = sum(signals[name] * weight for name, weight in weights.items())
    enough_text = min(_word_count(before), _word_count(after)) >= 250
    anchor_count = sum(signals[name] >= threshold for name, threshold in (
        ("title", 0.34), ("principal_entities", 0.12), ("topic_keywords", 0.16),
        ("source_families", 0.15), ("substantial_text_overlap", 0.12)))
    if not enough_text:
        outcome = "insufficient_evidence"
        reason = "One or both files are too short for a reliable article-identity decision."
    elif score >= 0.25 or anchor_count >= 3 or (
            signals["title"] >= 0.50 and anchor_count >= 2):
        outcome = "same_story"
        reason = "Multiple identity signals support an editorial revision of the same underlying story."
    elif score < 0.14 and anchor_count <= 1:
        outcome = "different_story"
        reason = "Title, topic, entity, source, heading, and overlap signals do not establish the same story."
    else:
        outcome = "ambiguous"
        reason = "The files share some identity signals, but human verification is advisable before learning."
    return {
        "outcome": outcome,
        "score": round(score, 3),
        "reason": reason,
        "draft_title": old_title,
        "final_title": new_title,
        "signals": {name: round(value, 3) for name, value in signals.items()},
    }


def _identity_diff_section(identity: dict, comparison_mode: str) -> str:
    signal_lines = "\n".join(
        f"- {name.replace('_', ' ').title()}: {value:.3f}"
        for name, value in identity["signals"].items())
    return (
        "## ARTICLE IDENTITY CHECK\n\n"
        f"- Comparison mode: `{comparison_mode}`\n"
        f"- Outcome: `{identity['outcome']}`\n"
        f"- Composite score: {identity['score']:.3f}\n"
        f"- Draft title: {identity['draft_title'] or '(missing)'}\n"
        f"- Final title: {identity['final_title'] or '(missing)'}\n"
        f"- Interpretation: {identity['reason']}\n\n"
        "### Signals\n\n" + signal_lines
    )


def build_editorial_diff(before: str, after: str, *, identity: dict | None = None,
                         comparison_mode: str = "editorial_revision") -> tuple[str, dict]:
    old_blocks, new_blocks = _blocks(before), _blocks(after)
    opcodes = SequenceMatcher(None, old_blocks, new_blocks, autojunk=False).get_opcodes()
    added, removed, replaced = [], [], []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "insert":
            added.extend(new_blocks[j1:j2])
        elif tag == "delete":
            removed.extend(old_blocks[i1:i2])
        elif tag == "replace":
            old_segment, new_segment = old_blocks[i1:i2], new_blocks[j1:j2]
            similarities = sorted(
                ((SequenceMatcher(None, old.casefold(), new.casefold()).ratio(), oi, nj)
                 for oi, old in enumerate(old_segment) for nj, new in enumerate(new_segment)),
                reverse=True)
            used_old, used_new = set(), set()
            for score, oi, nj in similarities:
                if score < 0.32 or oi in used_old or nj in used_new:
                    continue
                used_old.add(oi)
                used_new.add(nj)
                replaced.append((old_segment[oi], new_segment[nj]))
            removed.extend(block for index, block in enumerate(old_segment) if index not in used_old)
            added.extend(block for index, block in enumerate(new_segment) if index not in used_new)

    old_headings, new_headings = _headings(before), _headings(after)
    added_headings = [h for h in new_headings if h not in old_headings]
    removed_headings = [h for h in old_headings if h not in new_headings]
    renamed = []
    for old in removed_headings:
        matches = [(SequenceMatcher(None, old.casefold(), new.casefold()).ratio(), new) for new in added_headings]
        if matches and max(matches)[0] >= 0.45:
            renamed.append((old, max(matches)[1]))
    shared = [h for h in old_headings if h in new_headings]
    reordered = [h for h in shared if old_headings.index(h) != new_headings.index(h)]

    old_entities, new_entities = _entities(before), _entities(after)
    only_final = sorted(set(new_entities) - set(old_entities), key=lambda x: (-new_entities[x], x))[:25]
    disappeared = sorted(set(old_entities) - set(new_entities), key=lambda x: (-old_entities[x], x))[:25]
    promoted = sorted((name for name in set(old_entities) & set(new_entities)
                       if new_entities[name] >= max(3, old_entities[name] * 2)),
                      key=lambda x: (-(new_entities[x] - old_entities[x]), x))[:20]
    diminished = sorted((name for name in set(old_entities) & set(new_entities)
                         if old_entities[name] >= max(3, new_entities[name] * 2)),
                        key=lambda x: (-(old_entities[x] - new_entities[x]), x))[:20]
    old_links, new_links = _links(before), _links(after)
    old_prose, new_prose = _prose_blocks(before), _prose_blocks(after)
    old_narrative, new_narrative = _narrative_prose(before), _narrative_prose(after)
    summary = {
        "draft_words": _word_count(before), "final_words": _word_count(after),
        "draft_sections": len(old_headings), "final_sections": len(new_headings),
        "draft_paragraphs": len(old_prose), "final_paragraphs": len(new_prose),
        "added_blocks": len(added), "removed_blocks": len(removed), "replaced_blocks": len(replaced),
    }
    sections = [
        "# EDITORIAL DIFF\n",
        "## SUMMARY\n\n" + "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary.items()),
    ]
    if identity is not None:
        sections.append(_identity_diff_section(identity, comparison_mode))
    sections.append(
        "## SECTION CHANGES\n\n"
        + f"### Original headings\n\n" + "\n".join(f"- {h}" for h in old_headings)
        + f"\n\n### Final headings\n\n" + "\n".join(f"- {h}" for h in new_headings)
        + f"\n\n### Added\n\n" + ("\n".join(f"- {h}" for h in added_headings) or "- None detected")
        + f"\n\n### Removed\n\n" + ("\n".join(f"- {h}" for h in removed_headings) or "- None detected")
        + f"\n\n### Possible renames\n\n" + ("\n".join(f"- {a} → {b}" for a, b in renamed) or "- None detected")
        + f"\n\n### Possible major reordering\n\n" + ("\n".join(f"- {h}" for h in reordered) or "- None detected")
    )
    for title, blocks in (("SIGNIFICANT ADDED BLOCKS", added), ("SIGNIFICANT REMOVED BLOCKS", removed)):
        content = []
        for index, block in enumerate(sorted(blocks, key=_word_count, reverse=True)[:15], 1):
            content.append(f"### {index}\n\n> {_format_excerpt(block).replace(chr(10), chr(10) + '> ')}")
        sections.append(f"## {title}\n\n" + ("\n\n".join(content) or "None detected."))
    pairs = []
    for index, (old, new) in enumerate(sorted(replaced, key=lambda pair: _word_count(pair[0]) + _word_count(pair[1]), reverse=True)[:15], 1):
        pairs.append(f"### Replacement {index}\n\n**Draft**\n\n> {_format_excerpt(old).replace(chr(10), chr(10) + '> ')}"
                     f"\n\n**Final**\n\n> {_format_excerpt(new).replace(chr(10), chr(10) + '> ')}")
    sections.append("## REPLACED BLOCKS\n\n" + ("\n\n".join(pairs) or "None detected."))
    sections.append("## OPENING COMPARISON\n\n### Draft\n\n" + "\n\n".join("> " + _format_excerpt(x) for x in old_prose[:3])
                    + "\n\n### Final\n\n" + "\n\n".join("> " + _format_excerpt(x) for x in new_prose[:3]))
    sections.append("## CONCLUSION COMPARISON\n\n### Draft\n\n" + "\n\n".join("> " + _format_excerpt(x) for x in old_narrative[-3:])
                    + "\n\n### Final\n\n" + "\n\n".join("> " + _format_excerpt(x) for x in new_narrative[-3:]))
    old_qual, new_qual = _qualification_sentences(before), _qualification_sentences(after)
    sections.append("## CAVEAT / QUALIFICATION CHANGES\n\n### Draft signals\n\n"
                    + ("\n".join(f"- {x}" for x in old_qual) or "- None detected")
                    + "\n\n### Final signals\n\n" + ("\n".join(f"- {x}" for x in new_qual) or "- None detected"))
    sections.append("## PARAGRAPH RHYTHM CHANGES\n\n```json\n" + json.dumps(
        {"draft": _paragraph_metrics(before), "final": _paragraph_metrics(after)}, indent=2, ensure_ascii=False) + "\n```")
    sections.append("## ENTITY / PERSON CHANGES\n\nEntity extraction is heuristic; use these as leads, not findings.\n\n"
                    + "### Appeared only in final\n\n" + ("\n".join(f"- {x} ({new_entities[x]})" for x in only_final) or "- None detected")
                    + "\n\n### Disappeared from final\n\n" + ("\n".join(f"- {x} ({old_entities[x]})" for x in disappeared) or "- None detected")
                    + "\n\n### Became more prominent\n\n" + ("\n".join(f"- {x}: {old_entities[x]} → {new_entities[x]}" for x in promoted) or "- None detected")
                    + "\n\n### Became less prominent\n\n" + ("\n".join(f"- {x}: {old_entities[x]} → {new_entities[x]}" for x in diminished) or "- None detected"))
    sections.append("## LINK / SOURCE CHANGES\n\n### Added links\n\n"
                    + ("\n".join(f"- [{new_links[u]}]({u})" for u in sorted(set(new_links) - set(old_links))) or "- None")
                    + "\n\n### Removed links\n\n"
                    + ("\n".join(f"- [{old_links[u]}]({u})" for u in sorted(set(old_links) - set(new_links))) or "- None"))
    return "\n\n".join(sections).rstrip() + "\n", summary


def _series_learning_context(root: Path, series_slug: str | None, project: Path) -> list[str]:
    if not series_slug:
        return []
    cfg = json.loads((root / "white_rabbit_codex_config.json").read_text(encoding="utf-8"))
    series = root / cfg.get("series_dir", "series_projects") / series_slug
    context = []
    for relative in ("shared_research/SERIES_THEMES.md", "SERIES_CONTINUITY.md"):
        if (series / relative).is_file():
            context.append((series / relative).relative_to(root).as_posix())
    manifest = series / "SERIES_MANIFEST.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            current = next((p for p in data.get("parts", []) if p.get("slug") == project.name), None)
            if current:
                for part in data["parts"]:
                    article = series / "articles" / part.get("slug", "") / "output/article.md"
                    if part.get("number", 999) < current.get("number", 0) and article.is_file():
                        context.append(article.relative_to(root).as_posix())
        except (ValueError, TypeError, KeyError):
            pass
    return context


def _learning_prompt(root: Path, folder: Path, key: str, *, series_slug: str | None,
                     project: Path, identity: dict, comparison_mode: str) -> str:
    relative = folder.relative_to(root).as_posix()
    memory = memory_dir(root).relative_to(root).as_posix()
    series_context = _series_learning_context(root, series_slug, project)
    part5 = ""
    if key.startswith("usaid-office-of-public-safety__part-05-operation-two-fold"):
        part5 = """
## Operation TWO-FOLD hypotheses to test

Test—do not assume—the following against the actual pair: personnel followed across
institutions; career paths used as institutional evidence; Garland Williams-type bridges;
the Swain / Tripodi / Baldwin chain; attributed participant testimony treated as evidence;
repetitive primary-source caveats reduced; the Anthony Triponi reversal preserved;
no-dismissals contradiction promoted; DEA prosecution/immunity connected to Part 3's
gatekeeper concept; research allowed to strengthen/change the thesis; explanation
compressed after the mechanism becomes clear. Reject any hypothesis the files do not support.
"""
    if comparison_mode == "story_replacement":
        identity_instruction = """
## Intentional story-replacement comparison

This pair is explicitly preserved as a story-replacement / series-scope comparison, not
an ordinary same-story editorial revision. Analyze why the selected story changed, but do
not infer that people, claims, sources, caveats or techniques deleted with the old story
were editorially rejected. Whole-story deletions are scope evidence only and must not
produce claim-level or global candidate learnings.
"""
    else:
        identity_instruction = """
## Article identity gate

The deterministic identity check classified this pair as an ordinary editorial revision.
Confirm that judgment during semantic analysis. If close reading shows that these are
actually different stories, stop ordinary preference learning, explain the mismatch in
the postmortem and require an explicitly marked story-replacement comparison instead.
"""
    return f"""# Codex semantic editorial-learning assignment: {key}

This is Stage 2 of a Codex-first, no-provider-API workflow. Python prepared the comparison;
Codex must now perform the semantic editorial analysis.

Read these revision files completely:
- {relative}/draft_before_human_edit.md
- {relative}/final_published.md
- {relative}/editorial_diff.md

Read the permanent editorial/evidence standards:
- {memory}/VOICE_CANON.md
- {memory}/ANTI_PATTERNS.md
- {memory}/EDITORIAL_LESSONS.md
- {memory}/GOLD_ARTICLES.json
- docs/WHITE_RABBIT_STYLE.md
- docs/RESEARCH_AND_EVIDENCE.md
{chr(10).join('- ' + path for path in series_context)}

Comparison mode: `{comparison_mode}`
Article identity outcome: `{identity['outcome']}` (score {identity['score']:.3f})
Draft title: {identity['draft_title'] or '(missing)'}
Final title: {identity['final_title'] or '(missing)'}
{identity_instruction}

DO NOT merely summarize the textual diff. Determine the editorial reasoning implied by
the human changes. Distinguish direct textual evidence from careful inference. Quote only
short representative passages. Do not assume every human change is a reusable improvement.

## Required semantic analysis

### Story discovery
Determine whether the central mystery, thesis, larger pattern or actual story changed.

### Connection discovery
Identify added/promoted people, agencies, companies, programs, career paths and rabbit
holes—including connections research should have discovered before story architecture.

### Reveal order
Identify what moved earlier/later, became a reveal rather than background, was unburied,
or gained a better setup/payoff relationship.

### Evidence treatment
Identify caveats added/removed, attribution replacing qualification, changes in reliance
on named testimony, strengthened/weakened claims and changed evidentiary weight.

### Voice
Identify formal/academic/AI prose made conversational, narrator presence, transitions,
questions, concrete replacements for abstractions, paragraph rhythm and compression.

### Series continuity
Identify callbacks, conceptual payoffs, reused reader frameworks and changes to the next
installment handoff. If this is standalone, say not applicable.

### Ending
Determine whether recap became implication and whether the final question/rabbit hole changed.

### Repeated human preferences
Infer what the human consistently rejected and consistently added as principles—not a
catalog of individual word substitutions.
{part5}
## Required outputs

Replace `{relative}/editorial_postmortem.md` with a substantive analysis using exactly
these level-two sections:

- EXECUTIVE FINDING
- WHAT THE ORIGINAL DRAFT GOT RIGHT
- WHAT CODEX MISSED
- THE STORY CHANGED
- CONNECTIONS THE HUMAN PROMOTED
- HOW EVIDENCE TREATMENT CHANGED
- HOW THE REVEAL ORDER CHANGED
- HOW THE VOICE CHANGED
- SERIES CALLBACKS AND PAYOFFS
- WHAT WAS CUT — AND WHY
- WHAT WAS ADDED — AND WHY
- REUSABLE LESSONS
- ARTICLE-SPECIFIC CHANGES THAT SHOULD NOT BECOME GLOBAL RULES
- QUESTIONS FOR HUMAN REVIEW

Analysis comes first; leave only genuinely ambiguous items as questions.

Replace `{relative}/candidate_learnings.json` with valid JSON using this shape:

```json
{{
  "schema_version": 2,
  "key": "{key}",
  "analysis_status": "analyzed",
  "automatic_promotion": false,
  "candidate_learnings": [
    {{
      "id": "short-stable-id",
      "category": "CONNECTION_ADDED",
      "lesson": "A reusable imperative lesson.",
      "evidence": "Concise article-specific evidence from the comparison.",
      "scope": "global",
      "confidence": "high",
      "status": "pending",
      "promote_to": "EDITORIAL_LESSONS.md"
    }}
  ]
}}
```

Allowed categories: {', '.join(sorted(CATEGORIES))}.
Allowed scopes: global, investigative, series, article-specific. Article-specific items
normally stay unpromoted. Allowed confidence: high, medium, low. Every candidate starts
pending. Never mark a candidate approved; approval belongs to the human. Never edit
VOICE_CANON.md, ANTI_PATTERNS.md or EDITORIAL_LESSONS.md in this analysis pass.

When both files are written, run `python codex_article.py learning-status {key}` and
report the status. Do not run promote-learnings.
"""


def _candidate_template(key: str) -> dict:
    return {"schema_version": 2, "key": key, "analysis_status": "awaiting_codex_analysis",
            "automatic_promotion": False, "candidate_learnings": []}


def _pending_index(root: Path, key: str, candidate: Path, status: str) -> Path:
    path = initialize(root) / "pending_learnings" / f"{key}.json"
    data = {"schema_version": 2, "key": key, "status": status,
            "candidate_file": candidate.relative_to(root).as_posix(), "automatic_promotion": False}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def prepare_learning(root: Path, project: Path, *, series_slug: str | None = None,
                     final_source: Path | None = None, key: str | None = None,
                     comparison_mode: str = "editorial_revision") -> dict:
    key = key or revision_key(project, series_slug=series_slug)
    if not REVISION_KEY_PATTERN.fullmatch(key):
        raise ValueError("Invalid revision key")
    if comparison_mode not in COMPARISON_MODES:
        raise ValueError(f"comparison_mode must be one of: {', '.join(sorted(COMPARISON_MODES))}")
    folder = initialize(root) / "revision_history" / key
    folder.mkdir(parents=True, exist_ok=True)
    draft = folder / "draft_before_human_edit.md"
    final = folder / "final_published.md"
    source = final_source or project / "output/article.md"
    if not draft.is_file():
        raise ValueError("No pre-human snapshot. Run snapshot/export before human editing.")
    before = draft.read_text(encoding="utf-8-sig")
    if not final.exists():
        if not source.is_file():
            raise ValueError("Final human article is missing")
        prospective_after = source.read_text(encoding="utf-8-sig")
        prospective_identity = assess_article_identity(before, prospective_after)
        if prospective_identity["outcome"] == "different_story" and comparison_mode != "story_replacement":
            raise ValueError(
                "Article identity check indicates different stories. Ordinary editorial learning is blocked "
                "before preserving the proposed final. Verify the final article or explicitly prepare this "
                "as comparison_mode='story_replacement'. "
                f"Draft title: {prospective_identity['draft_title']!r}; "
                f"final title: {prospective_identity['final_title']!r}; "
                f"score: {prospective_identity['score']:.3f}."
            )
        shutil.copyfile(source, final)
    after = final.read_text(encoding="utf-8-sig")
    if before == after:
        raise ValueError("The preserved draft and final article are identical; there are no revisions to learn from.")
    identity = assess_article_identity(before, after)
    if identity["outcome"] == "different_story" and comparison_mode != "story_replacement":
        raise ValueError(
            "Article identity check indicates different stories. Ordinary editorial learning is blocked. "
            "Verify the final article or explicitly prepare this as comparison_mode='story_replacement'. "
            f"Draft title: {identity['draft_title']!r}; final title: {identity['final_title']!r}; "
            f"score: {identity['score']:.3f}."
        )
    diff_text, summary = build_editorial_diff(
        before, after, identity=identity, comparison_mode=comparison_mode)
    diff_path = folder / "editorial_diff.md"
    diff_path.write_text(diff_text, encoding="utf-8")
    prompt = folder / "LEARNING_PROMPT.md"
    prompt.write_text(_learning_prompt(root, folder, key, series_slug=series_slug, project=project,
                                       identity=identity, comparison_mode=comparison_mode), encoding="utf-8")
    postmortem = folder / "editorial_postmortem.md"
    candidate = folder / "candidate_learnings.json"
    existing_candidates = None
    if candidate.is_file():
        try:
            existing_candidates = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_candidates = None
    semantic_done = (postmortem.is_file()
                     and re.search(r"(?m)^## EXECUTIVE FINDING\s*$", postmortem.read_text(encoding="utf-8-sig"))
                     and isinstance(existing_candidates, dict)
                     and existing_candidates.get("analysis_status") == "analyzed")
    if not semantic_done:
        postmortem.write_text(
            f"# EDITORIAL POSTMORTEM\n\nSTATUS: AWAITING CODEX ANALYSIS\n\n"
            f"The deterministic comparison is prepared. Give `{prompt.relative_to(root).as_posix()}` to Codex. "
            "Codex must replace this placeholder with semantic editorial analysis before human review.\n",
            encoding="utf-8")
        candidate.write_text(json.dumps(_candidate_template(key), indent=2) + "\n", encoding="utf-8")
    prepared_status = "AWAITING_HUMAN_REVIEW" if semantic_done else "AWAITING_CODEX_ANALYSIS"
    pending = _pending_index(root, key, candidate, prepared_status)
    metadata = folder / "metadata.json"
    existing = json.loads(metadata.read_text(encoding="utf-8")) if metadata.is_file() else {}
    existing.update({"project": project.name, "series": series_slug, "key": key,
                     "learning_prepared_at": _now(), "diff_summary": summary,
                     "comparison_mode": comparison_mode, "article_identity": identity})
    metadata.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    current_status = learning_status(root, key)["status"] if semantic_done else "AWAITING_CODEX_ANALYSIS"
    return {"key": key, "status": current_status, "revision_dir": str(folder),
            "editorial_diff": str(diff_path), "learning_prompt": str(prompt),
            "postmortem": str(postmortem), "candidate_learnings": str(candidate),
            "pending_index": str(pending), "comparison_mode": comparison_mode,
            "article_identity": identity, **summary}


def seed_comparison(root: Path, key: str, draft_source: Path, final_source: Path, *,
                    comparison_mode: str = "editorial_revision",
                    series_slug: str | None = None, project: Path | None = None) -> dict:
    """Preserve a historical pair, then prepare—not fabricate—semantic analysis."""
    if not REVISION_KEY_PATTERN.fullmatch(key):
        raise ValueError("Invalid revision key")
    if not draft_source.is_file() or not final_source.is_file():
        raise ValueError("Both historical draft and final article must exist")
    folder = initialize(root) / "revision_history" / key
    folder.mkdir(parents=True, exist_ok=True)
    draft, final = folder / "draft_before_human_edit.md", folder / "final_published.md"
    if not draft.exists():
        shutil.copyfile(draft_source, draft)
    if not final.exists():
        shutil.copyfile(final_source, final)
    key_parts = key.split("__")
    if project is None:
        inferred_series = key_parts[0] if len(key_parts) >= 2 else None
        project_slug = key_parts[1] if len(key_parts) >= 2 else key_parts[0]
        series_slug = series_slug or inferred_series
        cfg = json.loads((root / "white_rabbit_codex_config.json").read_text())
        if series_slug:
            project = root / cfg.get("series_dir", "series_projects") / series_slug / "articles" / project_slug
        else:
            project = root / cfg["projects_dir"] / project_slug
    return prepare_learning(root, project, series_slug=series_slug, final_source=final, key=key,
                            comparison_mode=comparison_mode)


def learn(root: Path, project: Path, *, series_slug: str | None = None, review: bool = False,
          comparison_mode: str = "editorial_revision") -> dict:
    # --review means prepare the packet for Codex and eventual human review; Python does no semantic analysis.
    return prepare_learning(root, project, series_slug=series_slug, comparison_mode=comparison_mode)


def _candidate_path(root: Path, key: str) -> tuple[Path, dict | None]:
    memory = initialize(root)
    canonical = memory / "revision_history" / key / "candidate_learnings.json"
    if canonical.is_file():
        return canonical, None
    legacy = memory / "pending_learnings" / f"{key}.json"
    if not legacy.is_file():
        raise ValueError(f"No learning record for {key}")
    data = json.loads(legacy.read_text(encoding="utf-8"))
    pointer = data.get("candidate_file") if isinstance(data, dict) else None
    if isinstance(pointer, str):
        target = (root / pointer).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ValueError("Pending learning index points to an invalid candidate file")
        return target, data
    return legacy, data  # schema-v1 compatibility: readable, but not promotable without migration/approval.


def validate_candidates(data: dict, *, allow_legacy: bool = True) -> list[str]:
    errors = []
    candidates = data.get("candidate_learnings") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        return ["candidate_learnings must be a list"]
    for index, candidate in enumerate(candidates, 1):
        if isinstance(candidate, str) and allow_legacy:
            errors.append(f"candidate {index} uses legacy string schema; convert it to an explicitly approved object")
            continue
        if not isinstance(candidate, dict):
            errors.append(f"candidate {index} must be an object")
            continue
        required = ("id", "category", "lesson", "evidence", "scope", "confidence", "status", "promote_to")
        for field in required:
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                errors.append(f"candidate {index}: nonempty {field} required")
        if candidate.get("category") not in CATEGORIES:
            errors.append(f"candidate {index}: invalid category")
        if candidate.get("scope") not in SCOPES:
            errors.append(f"candidate {index}: invalid scope")
        if candidate.get("confidence") not in CONFIDENCE:
            errors.append(f"candidate {index}: invalid confidence")
        if candidate.get("status") not in STATUSES:
            errors.append(f"candidate {index}: invalid status")
        if candidate.get("promote_to") != "EDITORIAL_LESSONS.md":
            errors.append(f"candidate {index}: promote_to must be EDITORIAL_LESSONS.md")
    return errors


def learning_status(root: Path, key: str) -> dict:
    if not REVISION_KEY_PATTERN.fullmatch(key):
        raise ValueError("Use an article slug or series__part revision key")
    folder = initialize(root) / "revision_history" / key
    required = {name: (folder / name).is_file() for name in (
        "draft_before_human_edit.md", "final_published.md", "editorial_diff.md", "LEARNING_PROMPT.md",
        "editorial_postmortem.md", "candidate_learnings.json")}
    if not required["draft_before_human_edit.md"] or not required["final_published.md"]:
        legacy = initialize(root) / "pending_learnings" / f"{key}.json"
        if legacy.is_file():
            data = json.loads(legacy.read_text(encoding="utf-8"))
            candidates = data.get("candidate_learnings", []) if isinstance(data, dict) else []
            return {"key": key, "status": "AWAITING_CODEX_ANALYSIS", "files": required,
                    "legacy_record": True,
                    "candidate_schema_errors": validate_candidates(data) if candidates else []}
        status = "DIFF_PREPARED" if required["editorial_diff.md"] else "NOT_PREPARED"
        return {"key": key, "status": status, "files": required}
    if required["editorial_diff.md"] and not required["LEARNING_PROMPT.md"]:
        return {"key": key, "status": "DIFF_PREPARED", "files": required}
    candidate, _ = _candidate_path(root, key)
    data = json.loads(candidate.read_text(encoding="utf-8"))
    candidates = data.get("candidate_learnings", []) if isinstance(data, dict) else []
    errors = validate_candidates(data) if candidates else []
    if data.get("status") == "promoted" or (candidates and all(
            isinstance(c, dict) and c.get("status") in {"promoted", "rejected"} for c in candidates)):
        status = "PROMOTED"
    elif any(isinstance(c, dict) and (c.get("status") == "approved" or c.get("approved") is True)
             and c.get("scope") != "article-specific" for c in candidates):
        status = "READY_FOR_PROMOTION"
    elif candidates and not errors:
        status = "AWAITING_HUMAN_REVIEW"
    else:
        postmortem = (folder / "editorial_postmortem.md").read_text(encoding="utf-8-sig") if required["editorial_postmortem.md"] else ""
        status = "ANALYZED" if postmortem and "AWAITING CODEX ANALYSIS" not in postmortem else "AWAITING_CODEX_ANALYSIS"
    return {"key": key, "status": status, "files": required, "candidate_schema_errors": errors,
            "candidate_count": len(candidates), "approved_count": sum(
                isinstance(c, dict) and (c.get("status") == "approved" or c.get("approved") is True)
                for c in candidates)}


def promote(root: Path, key: str) -> dict:
    if not REVISION_KEY_PATTERN.fullmatch(key):
        raise ValueError("Use an article slug or series__part revision key")
    candidate_path, _ = _candidate_path(root, key)
    data = json.loads(candidate_path.read_text(encoding="utf-8"))
    errors = validate_candidates(data)
    if errors:
        raise ValueError("Candidate-learning schema errors:\n" + "\n".join(errors))
    candidates = data["candidate_learnings"]
    approved = [candidate for candidate in candidates
                if (candidate.get("status") == "approved" or candidate.get("approved") is True)
                and candidate.get("scope") != "article-specific"]
    if not approved:
        raise ValueError("No explicitly approved, non-article-specific candidates are ready for promotion")
    destination = initialize(root) / "EDITORIAL_LESSONS.md"
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(f"\n\n## Approved learning: {key}\n\n")
        for candidate in approved:
            handle.write(f"- **{candidate['category']} / {candidate['scope']}:** {candidate['lesson'].strip()}\n")
            candidate["status"] = "promoted"
            candidate.pop("approved", None)
    data.update(status="promoted" if all(c.get("status") in {"promoted", "rejected", "pending"} for c in candidates)
                else data.get("status"), promoted_at=_now())
    candidate_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _pending_index(root, key, candidate_path, "PROMOTED")
    return {"key": key, "promoted": len(approved), "destination": str(destination),
            "remaining_pending": sum(c.get("status") == "pending" for c in candidates)}
