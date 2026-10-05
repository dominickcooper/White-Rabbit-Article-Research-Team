from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .archive_db import ArchiveDB, ArchiveArticle


_UI_PHRASES = (
    "read full story", "continue reading this post", "purchase a paid subscription",
    "subscribe for free", "to receive new posts and support my work", "share this post",
    "leave a comment", "the white rabbit report's avatar", "user's avatar",
)
_STOP = {
    "the", "and", "that", "this", "with", "from", "have", "were", "was", "are", "for",
    "into", "about", "what", "when", "where", "which", "who", "why", "how", "not", "but",
    "its", "their", "they", "them", "then", "than", "there", "here", "your", "you", "our",
    "out", "all", "can", "could", "would", "should", "article", "investigative", "investigation",
}


@dataclass(frozen=True)
class VoicePassage:
    article: ArchiveArticle
    paragraph_number: int
    section: str
    text: str
    score: float
    traits: tuple[str, ...]
    gold_exemplar: bool


@dataclass(frozen=True)
class VoiceSearchResult:
    passages: tuple[VoicePassage, ...]
    articles_scanned: int
    full_articles_scanned: int
    partial_articles_excluded: int
    quotation_blocks_excluded: int
    ui_blocks_excluded: int
    prose_blocks_considered: int


def _plain(markdown: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def extract_authored_paragraphs(markdown: str) -> tuple[list[tuple[int, str, str]], dict[str, int]]:
    """Return paragraph-level authored prose while excluding quotations and Substack UI."""
    heading = "Opening"
    paragraphs: list[tuple[int, str, str]] = []
    stats = {"quotation_blocks_excluded": 0, "ui_blocks_excluded": 0}
    for block in re.split(r"\n\s*\n", markdown.replace("\r\n", "\n")):
        raw = block.strip()
        if not raw:
            continue
        if raw.startswith("#"):
            candidate = re.sub(r"^#{1,6}\s*", "", raw).strip()
            if candidate:
                heading = _plain(candidate)
            continue
        low = raw.casefold()
        if raw.startswith(">") or all(line.lstrip().startswith(">") for line in raw.splitlines()):
            stats["quotation_blocks_excluded"] += 1
            continue
        if raw.startswith(("![", "[![", "|", "- ", "* ", "1. ")):
            stats["ui_blocks_excluded"] += 1
            continue
        if any(phrase in low for phrase in _UI_PHRASES):
            stats["ui_blocks_excluded"] += 1
            continue
        text = _plain(raw)
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)
        if len(words) < 18 or len(words) > 240:
            continue
        paragraphs.append((len(paragraphs) + 1, heading, text))
    return paragraphs, stats


def _tokens(text: str) -> Counter[str]:
    return Counter(
        token for token in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", text.casefold())
        if token not in _STOP
    )


def _traits(text: str) -> tuple[str, ...]:
    traits: list[str] = []
    sentences = re.findall(r"[^.!?]+[.!?]", text)
    if "?" in text:
        traits.append("fact creates an investigative question")
    if re.search(r"\b(?:I|my|we)\b", text):
        traits.append("investigator visibly present")
    if re.search(r"\b(?:document|memo|file|record|report|email|contract|testified|told)\b", text, re.I):
        traits.append("documentary receipt drives the prose")
    if re.search(r"\b(?:but|except|then|now|weird|interesting|except)\b", text, re.I):
        traits.append("blunt turn or reveal")
    if 2 <= len(sentences) <= 6:
        traits.append("natural multi-sentence paragraph rhythm")
    if not traits:
        traits.append("concrete explanatory prose")
    return tuple(traits[:3])


def _normalized_title(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold().replace("’s", "").replace("'s", "")))


def _gold_titles(root: Path | None) -> set[str]:
    if root is None:
        return set()
    path = root / "research_library" / "editorial_memory" / "GOLD_ARTICLES.json"
    if not path.is_file():
        return set()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {_normalized_title(str(row.get("title", ""))) for row in rows if row.get("approved")}


def _is_gold_title(title: str, gold_titles: set[str]) -> bool:
    normalized = _normalized_title(title)
    tokens = set(normalized.split())
    for gold in gold_titles:
        if not gold:
            continue
        if gold in normalized or normalized in gold:
            return True
        gold_tokens = set(gold.split())
        if len(tokens & gold_tokens) >= 3 and len(tokens & gold_tokens) / max(1, len(gold_tokens)) >= 0.5:
            return True
    return False


def retrieve_voice_references(
    db_path: Path,
    query: str,
    *,
    root: Path | None = None,
    passage_limit: int = 8,
    per_article_limit: int = 2,
) -> VoiceSearchResult:
    db_path = Path(db_path)
    if not db_path.is_file():
        return VoiceSearchResult((), 0, 0, 0, 0, 0, 0)
    db = ArchiveDB(db_path)
    try:
        articles = db.list_articles()
    finally:
        db.close()
    query_tokens = _tokens(query)
    gold_titles = _gold_titles(root)
    candidates: list[VoicePassage] = []
    full = partial = quote_excluded = ui_excluded = prose = 0
    for article in articles:
        if article.content_status != "full":
            partial += 1
            continue
        article_path = Path(article.local_dir) / "article.md"
        if not article_path.is_file():
            continue
        full += 1
        body = article_path.read_text(encoding="utf-8-sig")
        paragraphs, stats = extract_authored_paragraphs(body)
        quote_excluded += stats["quotation_blocks_excluded"]
        ui_excluded += stats["ui_blocks_excluded"]
        prose += len(paragraphs)
        title_tokens = _tokens(article.title)
        is_gold = _is_gold_title(article.title, gold_titles)
        for number, section, text in paragraphs:
            tokens = _tokens(text)
            overlap = sum(min(tokens[t], query_tokens[t]) for t in query_tokens)
            title_overlap = sum(min(title_tokens[t], query_tokens[t]) for t in query_tokens)
            specificity = overlap / max(1.0, sum(query_tokens.values()))
            subject_match = False
            score = specificity + 0.22 * title_overlap
            if re.search(r"\b(?:CIA|intelligence|contractor|network|operation|agency)\b", query, re.I):
                if re.search(r"\b(?:CIA|intelligence|contractor|network|operation|agency)\b", text, re.I):
                    subject_match = True
                    score += 0.22
            if is_gold and (overlap or title_overlap or subject_match):
                score += 0.35
            if score <= 0 and not is_gold:
                continue
            candidates.append(VoicePassage(
                article=article,
                paragraph_number=number,
                section=section,
                text=text,
                score=score,
                traits=_traits(text),
                gold_exemplar=is_gold,
            ))
    candidates.sort(key=lambda item: (item.score, item.gold_exemplar, item.article.word_count), reverse=True)
    selected: list[VoicePassage] = []
    by_article: Counter[str] = Counter()
    for candidate in candidates:
        if by_article[candidate.article.canonical_url] >= per_article_limit:
            continue
        selected.append(candidate)
        by_article[candidate.article.canonical_url] += 1
        if len(selected) >= passage_limit:
            break
    return VoiceSearchResult(
        tuple(selected), len(articles), full, partial, quote_excluded, ui_excluded, prose
    )


def format_voice_reference_packet(result: VoiceSearchResult) -> str:
    if not result.passages:
        return "# WHITE RABBIT VOICE REFERENCES\n\n(No full authored passages were available.)"
    out = [
        "# WHITE RABBIT VOICE REFERENCES — AUTHORED PROSE ONLY\n\n",
        "Use these paragraphs for cadence, investigative movement, explanation, and reveal structure. "
        "Do not copy distinctive phrases. Quoted material, blockquotes, related-post cards, paywall text, "
        "subscription UI, and partial-preview articles were excluded from this voice packet.\n\n",
    ]
    for idx, passage in enumerate(result.passages, 1):
        article = passage.article
        out.append(f"## Voice example {idx}: {article.title}\n")
        out.append(f"Published article: {article.canonical_url}\n")
        out.append(f"Archive body: {Path(article.local_dir) / 'article.md'}\n")
        out.append(f"Location: {passage.section}, authored paragraph {passage.paragraph_number}\n")
        out.append(f"Why relevant: {'; '.join(passage.traits)}\n")
        out.append(f"Gold exemplar: {'yes' if passage.gold_exemplar else 'no'}\n")
        out.append(f"Authored passage:\n{passage.text}\n\n")
    out.append(
        "Extraction audit: "
        f"{result.full_articles_scanned} full articles scanned; "
        f"{result.partial_articles_excluded} partial articles excluded; "
        f"{result.quotation_blocks_excluded} quotation blocks excluded; "
        f"{result.ui_blocks_excluded} UI/non-prose blocks excluded.\n"
    )
    return "".join(out)
