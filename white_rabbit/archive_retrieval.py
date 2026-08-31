from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .archive_db import ArchiveDB, ArchiveArticle

INDEX_VERSION = 4
_INDEX_FILENAME = "archive_search_index_v4.joblib"

_STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "between", "both", "but", "by", "can",
    "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
    "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    "yours", "yourself", "yourselves",
}

_BOILERPLATE_PATTERNS = (
    r"thanks for reading the white rabbit report[^\n]*",
    r"this substack is reader-supported[^\n]*",
    r"subscribe for free[^\n]*",
    r"to receive new posts and support my work[^\n]*",
    r"consider becoming a free or paid subscriber[^\n]*",
    r"share this post[^\n]*",
    r"leave a comment[^\n]*",
    r"restacks?[^\n]*",
)


@dataclass(frozen=True)
class IndexedChunk:
    article_url: str
    wr_id: str
    title: str
    published_date: str | None
    content_status: str
    section: str
    text: str
    token_count: int
    external_links: tuple[tuple[str, str], ...]
    internal_links: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ArchiveMemory:
    article: ArchiveArticle
    excerpt: str
    score: float
    links: list[dict]
    matched_terms: tuple[str, ...] = ()
    exact_phrases: tuple[str, ...] = ()
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    phrase_score: float = 0.0
    best_section: str = ""
    research_source_count: int = 0
    internal_link_count: int = 0
    connection_type: str = "background connection"
    query_entities: tuple[str, ...] = ()
    expanded_concepts: tuple[str, ...] = ()
    concept_score: float = 0.0
    concept_hits: tuple[str, ...] = ()
    cooccurrence_score: float = 0.0
    connection_tier: str = "background"
    preview_penalty: float = 1.0
    shared_infrastructure: tuple[str, ...] = ()


def _tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.&'-]{1,}", text)
        if t.lower() not in _STOPWORDS
    ]


def _strip_md_images(text: str) -> str:
    text = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    return text


def _strip_markdown_links_keep_anchor(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\((?:https?://|mailto:)[^)]+\)", r"\1", text)


def clean_article_markdown(markdown: str, title: str = "") -> str:
    """Create a search-safe version without mutating the archived article.

    The downloaded Markdown remains the archival copy. This cleaner removes the
    most common Substack navigation/profile/image/CTA chrome while preserving
    headings, article prose, quotation text, and link anchor words.
    """
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")

    # If an H1 exists, discard publication navigation that precedes the article title.
    h1_matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", text))
    if h1_matches:
        chosen = h1_matches[0]
        if title:
            title_norm = re.sub(r"\W+", " ", title).strip().lower()
            for m in h1_matches:
                cand = re.sub(r"\W+", " ", m.group(1)).strip().lower()
                if cand and (cand in title_norm or title_norm in cand):
                    chosen = m
                    break
        text = text[chosen.start():]

    text = _strip_md_images(text)

    # Remove publication/profile links that frequently appear in the byline chrome.
    text = re.sub(
        r"\[(?:The White Rabbit Report|Shadow Reports|Current Events|Big Pharma|The Deep State)\]"
        r"\((?:https?://)?(?:www\.)?(?:thewhiterabbitreport\.substack\.com/s/[^)]*|substack\.com/(?:@|profile/)[^)]*)\)",
        " ",
        text,
        flags=re.I,
    )

    # Remove common Substack CDN / avatar link remnants that markdownify can leave behind.
    text = re.sub(r"\[[^\]]*\]\(https?://(?:substackcdn\.com|substack-post-media\.s3\.amazonaws\.com)[^)]+\)", " ", text, flags=re.I)

    for pat in _BOILERPLATE_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.I)

    # Lines that are just author/date/share chrome.
    cleaned_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if not line:
            cleaned_lines.append("")
            continue
        if low in {"the white rabbit report", "share", "subscribe", "comments", "restack"}:
            continue
        if re.fullmatch(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},\s+20\d{2}", line, flags=re.I):
            continue
        if "substackcdn.com/image/fetch" in low or "substack-post-media.s3.amazonaws.com" in low:
            continue
        cleaned_lines.append(raw)

    text = "\n".join(cleaned_lines)
    text = _strip_markdown_links_keep_anchor(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



_JUNK_ANCHORS = {
    "share", "share this post", "read full story", "subscribe", "subscription",
    "comments", "comment", "restack", "the white rabbit report", "sign in", "sign up",
    "manage subscription", "download app", "open in app",
}

_GENERIC_QUERY_TERMS = {
    "safety", "security", "government", "state", "public", "system", "systems",
    "network", "networks", "technology", "technologies", "data", "information",
    "report", "reports", "article", "articles", "program", "programs",
}

# Words that are too generic, rhetorical, or structurally common to become
# archive-derived expansion concepts on their own. Multi-word phrases may still
# contain some of these when the combination is specific (e.g. "camera network").
_CONCEPT_HARD_JUNK = {"people", "money", "brings", "bring", "thing", "things", "discussion", "example", "examples"}

_CONCEPT_JUNK_SINGLE = _GENERIC_QUERY_TERMS | {
    "people", "money", "brings", "bring", "thing", "things", "look", "looking",
    "question", "questions", "example", "examples", "use", "used", "using",
    "works", "work", "today", "years", "way", "ways", "new", "old", "part",
    "case", "cases", "story", "stories", "article", "section", "point", "points",
    "patent", "camera", "cameras", "surveillance", "company", "companies",
}

# General investigative/infrastructure vocabulary used only as a co-occurrence
# signal. A single word from this list is never sufficient to admit a conceptual
# result; combinations are what matter.
_INFRASTRUCTURE_TERMS = {
    "tracking", "location", "locations", "vehicle", "vehicles", "plate", "plates",
    "license", "reader", "readers", "alpr", "police", "law", "enforcement",
    "database", "databases", "analytics", "integration", "integrated", "networked",
    "jurisdiction", "jurisdictions", "sightings", "movement", "movements", "roads",
    "roadside", "infrared", "sensor", "sensors", "searchable", "intelligence",
}


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9&.'_-]+", " ", text)).strip().lower()


def _is_junk_anchor(anchor: str) -> bool:
    low = re.sub(r"\s+", " ", (anchor or "").strip()).lower().strip("#*_-: ")
    if not low:
        return True
    if low in _JUNK_ANCHORS:
        return True
    if low.startswith("share ") or low.startswith("subscribe "):
        return True
    return False


def _canonical_internal_url(url: str) -> str:
    """Normalize White Rabbit /p/ links and strip Substack tracking/share parameters."""
    try:
        parts = urlsplit(url.strip())
    except Exception:
        return url.strip()
    path = (parts.path or "/").rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), path, "", ""))


def _detect_query_entities(query: str) -> tuple[str, ...]:
    """Detect explicit named entities without an LLM.

    Consecutive TitleCase words form a named entity (``Flock Safety``). ALLCAPS
    acronyms are treated as their own entity (``ALPR``) rather than being glued
    onto the preceding proper name. Quoted multi-word phrases are also entities.
    """
    entities: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        norm = _normalize_phrase(value)
        if norm and norm not in seen:
            entities.append(norm)
            seen.add(norm)

    for q in re.findall(r'["“]([^"”]{2,80})["”]', query):
        if len(_tokenize(q)) >= 2:
            add(q)

    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.&'-]*", query)
    title_run: list[str] = []

    def flush_title_run() -> None:
        nonlocal title_run
        if len(title_run) >= 2:
            add(" ".join(title_run))
        title_run = []

    for tok in toks:
        if tok.isupper() and len(tok) >= 2:
            flush_title_run()
            add(tok)
            continue
        if tok[:1].isupper() and not tok.isupper():
            title_run.append(tok)
            continue
        flush_title_run()
    flush_title_run()
    return tuple(entities)

def _query_plan(query: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    entities = _detect_query_entities(query)
    entity_components = {w for e in entities for w in _tokenize(e)}
    all_tokens = _tokenize(query)
    free_terms = tuple(t for t in all_tokens if t not in entity_components)
    # Avoid giving generic component words from a named entity independent weight.
    if not free_terms and not entities:
        free_terms = tuple(all_tokens)
    return entities, tuple(sorted(entity_components)), free_terms


def _expanded_concepts(index: dict, entities: tuple[str, ...], query: str, *, limit: int = 18) -> tuple[str, ...]:
    """Derive meaningful phrases from chunks that directly mention the entity.

    Retrieval v4 refuses to promote generic discourse words such as ``patent``,
    ``camera``, ``people`` or ``brings`` into expansion concepts on their own.
    It prefers multi-word phrases and rare/technical single terms such as ALPR,
    infrared, or a patent identifier. This remains entirely local.
    """
    if not entities:
        return ()
    chunks: list[dict] = index.get("chunks", [])
    vectorizer = index.get("vectorizer")
    if not chunks or vectorizer is None:
        return ()

    seed_idx: list[int] = []
    for i, c in enumerate(chunks):
        hay = f"{c['title']} {c['section']} {c['text']}".lower()
        if any(e in hay for e in entities):
            seed_idx.append(i)
    if not seed_idx:
        return ()

    texts = [f"{chunks[i]['title']} {chunks[i]['section']} {chunks[i]['text']}" for i in seed_idx[:60]]
    mat = vectorizer.transform(texts)
    weights = mat.mean(axis=0)
    arr = np.asarray(weights).reshape(-1)
    features = vectorizer.get_feature_names_out()
    query_words = set(_tokenize(query))
    entity_words = {w for e in entities for w in _tokenize(e)}
    all_hays = [f"{c['title']} {c['section']} {c['text']}".lower() for c in chunks]
    total = max(1, len(all_hays))

    candidates: list[tuple[float, str]] = []
    for idx in np.argsort(arr)[::-1][:1200]:
        base = float(arr[idx])
        if base <= 0:
            break
        feat = _normalize_phrase(str(features[idx]))
        ftoks = _tokenize(feat)
        if not ftoks or len(feat) < 3:
            continue
        if set(ftoks).issubset(query_words | entity_words):
            continue
        if any(t in entity_words for t in ftoks):
            continue
        if any(t in _STOPWORDS for t in ftoks):
            continue

        df = sum(1 for hay in all_hays if feat in hay)
        df_ratio = df / total
        token_count = len(ftoks)

        if token_count == 1:
            tok = ftoks[0]
            technical = (
                tok in _INFRASTRUCTURE_TERMS
                or bool(re.search(r"\d", tok))
                or (len(tok) <= 6 and tok.isalpha() and tok not in _CONCEPT_JUNK_SINGLE and df_ratio <= 0.10)
                or (len(tok) >= 7 and tok not in _CONCEPT_JUNK_SINGLE and df_ratio <= 0.14)
            )
            if tok in _CONCEPT_JUNK_SINGLE or not technical:
                continue
        else:
            if any(t in _CONCEPT_HARD_JUNK for t in ftoks):
                continue
            informative = [t for t in ftoks if t not in _CONCEPT_JUNK_SINGLE]
            if not informative:
                continue
            if token_count >= 3 and not (sum(t in _INFRASTRUCTURE_TERMS for t in ftoks) >= 2 or any(re.search(r"\d", t) for t in ftoks)):
                continue
            if token_count == 2 and len(informative) == 1 and informative[0] in {"money", "people", "brings", "thing"}:
                continue

        rarity = min(3.0, math.log((total + 1) / (df + 1)) + 1.0)
        phrase_boost = 1.0 + 0.42 * min(2, token_count - 1)
        specificity = 1.15 if any(t in _INFRASTRUCTURE_TERMS for t in ftoks) else 1.0
        if any(re.search(r"\d", t) for t in ftoks):
            specificity += 0.15
        candidates.append((base * rarity * phrase_boost * specificity, feat))

    candidates.sort(reverse=True)
    concepts: list[str] = []
    seen: set[str] = set()
    for _, feat in candidates:
        if feat in seen:
            continue
        if any(feat != existing and feat in existing and len(_tokenize(feat)) == 1 for existing in concepts):
            continue
        concepts.append(feat)
        seen.add(feat)
        if len(concepts) >= limit:
            break
    return tuple(concepts)


def _dedupe_concept_hits(hits: list[str]) -> tuple[str, ...]:
    ordered = sorted(dict.fromkeys(hits), key=lambda x: (-len(_tokenize(x)), -len(x), x))
    kept: list[str] = []
    for hit in ordered:
        if any(hit != k and hit in k for k in kept):
            continue
        kept.append(hit)
    return tuple(kept)


def _concept_score_for_chunk(chunk: dict, concepts: tuple[str, ...]) -> tuple[float, tuple[str, ...], float]:
    if not concepts:
        return 0.0, (), 0.0
    hay = f"{chunk['title']} {chunk['section']} {chunk['text']}".lower()
    raw_hits = [c for c in concepts if c in hay]
    hits = _dedupe_concept_hits(raw_hits)
    if not hits:
        return 0.0, (), 0.0

    weighted = 0.0
    for hit in hits[:10]:
        toks = _tokenize(hit)
        if len(toks) >= 3:
            weighted += 1.9
        elif len(toks) == 2:
            weighted += 1.55
        elif toks and toks[0] in _INFRASTRUCTURE_TERMS:
            weighted += 1.0
        else:
            weighted += 0.75
    score = min(1.0, weighted / 4.0)

    distinct = len(hits)
    has_phrase = any(len(_tokenize(h)) >= 2 for h in hits)
    cooccurrence = min(1.0, max(0, distinct - 1) * 0.34 + (0.25 if has_phrase else 0.0))
    return score, hits[:10], cooccurrence


def classify_link(url: str, canonical_article_url: str) -> str:
    """Classify an archived hyperlink for retrieval use."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return "ignored"
    try:
        target = urlsplit(url)
        article = urlsplit(canonical_article_url)
    except Exception:
        return "ignored"

    host = target.netloc.lower().split(":", 1)[0]
    article_host = article.netloc.lower().split(":", 1)[0]
    path = target.path or "/"

    if host in {"substackcdn.com", "substack-post-media.s3.amazonaws.com"} or host.endswith("substackcdn.com"):
        return "ignored"
    if host == "substack.com" or host.endswith(".substack.com"):
        if host == article_host and path.startswith("/p/"):
            return "internal_article"
        return "ignored"
    if host == article_host:
        if path.startswith("/p/"):
            return "internal_article"
        return "ignored"
    return "external_research"

def _extract_markdown_links(markdown: str, canonical_article_url: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    external: list[tuple[str, str]] = []
    internal: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    current_internal = _canonical_internal_url(canonical_article_url)
    for m in re.finditer(r"\[([^\]]{1,300})\]\((https?://[^)\s]+)\)", markdown):
        anchor = re.sub(r"\s+", " ", m.group(1)).strip()
        url = m.group(2).strip()
        if not anchor or not url or _is_junk_anchor(anchor):
            continue
        kind = classify_link(url, canonical_article_url)
        if kind == "internal_article":
            url = _canonical_internal_url(url)
            if url == current_internal:
                continue
        key = (anchor.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        if kind == "external_research":
            external.append((anchor, url))
        elif kind == "internal_article":
            internal.append((anchor, url))
    return external, internal

def _raw_markdown_sections(markdown: str, article_title: str) -> list[tuple[str, str]]:
    """Split raw Markdown into heading-scoped bodies while preserving links."""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    h1_matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", text))
    if h1_matches:
        chosen = h1_matches[0]
        if article_title:
            title_norm = re.sub(r"\W+", " ", article_title).strip().lower()
            for m in h1_matches:
                cand = re.sub(r"\W+", " ", m.group(1)).strip().lower()
                if cand and (cand in title_norm or title_norm in cand):
                    chosen = m
                    break
        text = text[chosen.start():]

    sections: list[tuple[str, str]] = []
    current_heading = article_title
    buf: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if heading:
            if buf:
                body = "\n".join(buf).strip()
                if body:
                    sections.append((current_heading, body))
                buf = []
            current_heading = heading.group(1).strip()
            continue
        buf.append(line)
    if buf:
        body = "\n".join(buf).strip()
        if body:
            sections.append((current_heading, body))
    return sections


def _links_relevant_to_piece(
    links: list[tuple[str, str]],
    piece: str,
    section_text: str,
) -> tuple[tuple[str, str], ...]:
    """Keep links whose anchor occurs in the current chunk/section.

    This is the key v4 change that prevents a Flock-matching section from
    returning every unrelated source used elsewhere in a long article.
    """
    piece_low = piece.lower()
    section_low = section_text.lower()
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor, url in links:
        a = re.sub(r"\s+", " ", anchor).strip()
        if not a or _is_junk_anchor(a):
            continue
        a_low = a.lower()
        # Exact anchor in the chunk is strongest. For very short/generic anchors,
        # require chunk-local presence; longer anchors may fall back to section.
        in_piece = a_low in piece_low
        in_section = a_low in section_low
        if not in_piece and not (len(_tokenize(a)) >= 2 and in_section and len(piece.split()) < 720):
            continue
        key = url
        if key in seen:
            continue
        seen.add(key)
        selected.append((a, url))
    return tuple(selected)


def _section_chunks(
    markdown: str,
    article: ArchiveArticle,
    registered_links: list[dict] | None = None,
    target_words: int = 650,
    overlap_words: int = 90,
) -> list[IndexedChunk]:
    raw_sections = _raw_markdown_sections(markdown, article.title)
    if not raw_sections:
        return []

    result: list[IndexedChunk] = []
    for section, raw_body in raw_sections:
        clean_body = clean_article_markdown(raw_body, "")
        clean_body = re.sub(r"\s+", " ", clean_body).strip()
        if not clean_body:
            continue

        external_links, internal_links = _extract_markdown_links(raw_body, article.canonical_url)
        seen_links = {(a.lower(), u) for a, u in external_links + internal_links}

        # DB-registered links are admitted only when their anchor is actually
        # present in this section. They are no longer attached article-wide.
        clean_low = clean_body.lower()
        for link in registered_links or []:
            anchor = re.sub(r"\s+", " ", str(link.get("anchor", ""))).strip()
            url = str(link.get("url", "")).strip()
            if not anchor or not url or _is_junk_anchor(anchor):
                continue
            if anchor.lower() not in clean_low:
                continue
            kind = classify_link(url, article.canonical_url)
            if kind == "internal_article":
                url = _canonical_internal_url(url)
                if url == _canonical_internal_url(article.canonical_url):
                    continue
            key = (anchor.lower(), url)
            if key in seen_links:
                continue
            if kind == "external_research":
                external_links.append((anchor, url))
                seen_links.add(key)
            elif kind == "internal_article":
                internal_links.append((anchor, url))
                seen_links.add(key)

        words = clean_body.split()
        if len(words) <= target_words:
            pieces = [clean_body]
        else:
            pieces = []
            step = max(1, target_words - overlap_words)
            for start in range(0, len(words), step):
                piece = " ".join(words[start:start + target_words]).strip()
                if piece:
                    pieces.append(piece)
                if start + target_words >= len(words):
                    break

        for piece in pieces:
            piece_external = _links_relevant_to_piece(external_links, piece, clean_body)
            piece_internal = _links_relevant_to_piece(internal_links, piece, clean_body)
            result.append(IndexedChunk(
                article_url=article.canonical_url,
                wr_id=article.wr_id,
                title=article.title,
                published_date=article.published_date,
                content_status=article.content_status,
                section=section,
                text=piece,
                token_count=len(_tokenize(piece)),
                external_links=piece_external,
                internal_links=piece_internal,
            ))
    return result


def _archive_signature(articles: Iterable[ArchiveArticle]) -> str:
    h = hashlib.sha256()
    h.update(f"index-v{INDEX_VERSION}".encode())
    for a in sorted(articles, key=lambda x: x.canonical_url):
        h.update(a.canonical_url.encode("utf-8", errors="ignore"))
        h.update(a.content_hash.encode("utf-8", errors="ignore"))
        h.update(a.content_status.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _index_path_for(db_path: Path) -> Path:
    return Path(db_path).parent / _INDEX_FILENAME


def rebuild_archive_search_index(db_path: Path, *, force: bool = False) -> dict:
    """Build cleaned chunk corpus + BM25 metadata + local latent-semantic vectors."""
    db_path = Path(db_path)
    db = ArchiveDB(db_path)
    try:
        articles = db.list_articles()
        registered_links = {a.canonical_url: db.links_for(a.canonical_url) for a in articles}
    finally:
        db.close()

    signature = _archive_signature(articles)
    index_path = _index_path_for(db_path)
    if index_path.exists() and not force:
        try:
            existing = joblib.load(index_path)
            if existing.get("version") == INDEX_VERSION and existing.get("signature") == signature:
                return {
                    "rebuilt": False,
                    "articles": existing.get("article_count", 0),
                    "chunks": len(existing.get("chunks", [])),
                    "index_path": str(index_path),
                }
        except Exception:
            pass

    chunks: list[IndexedChunk] = []
    indexed_articles = 0
    for article in articles:
        article_path = Path(article.local_dir) / "article.md"
        if not article_path.exists():
            continue
        raw = article_path.read_text(encoding="utf-8", errors="ignore")
        article_chunks = _section_chunks(raw, article, registered_links.get(article.canonical_url, []))
        if article_chunks:
            indexed_articles += 1
            chunks.extend(article_chunks)

    texts = [f"{c.title}. {c.section}. {c.text}" for c in chunks]
    vectorizer = None
    svd = None
    semantic_matrix = None
    if texts:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.98 if len(texts) >= 3 else 1.0,
            max_features=30000,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        matrix = vectorizer.fit_transform(texts)
        max_components = min(128, matrix.shape[0] - 1, matrix.shape[1] - 1)
        if max_components >= 2:
            svd = TruncatedSVD(n_components=max_components, random_state=42)
            semantic_matrix = normalize(svd.fit_transform(matrix))
        else:
            semantic_matrix = normalize(matrix).toarray()

    payload = {
        "version": INDEX_VERSION,
        "signature": signature,
        "article_count": indexed_articles,
        "chunks": [asdict(c) for c in chunks],
        "vectorizer": vectorizer,
        "svd": svd,
        "semantic_matrix": semantic_matrix,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, index_path, compress=3)
    return {
        "rebuilt": True,
        "articles": indexed_articles,
        "chunks": len(chunks),
        "index_path": str(index_path),
    }


def _load_index(db_path: Path) -> dict:
    rebuild_archive_search_index(db_path, force=False)
    return joblib.load(_index_path_for(db_path))


def _query_phrases(query: str, entities: tuple[str, ...] = ()) -> list[str]:
    entity_words = {w for e in entities for w in _tokenize(e)}
    raw_words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.&'-]*", query)]
    phrases: list[str] = list(entities)
    for n in (4, 3, 2):
        for i in range(0, len(raw_words) - n + 1):
            piece = raw_words[i:i + n]
            # Do not manufacture phrases such as "safety surveillance" out of
            # a component of the named entity "Flock Safety".
            if any(w in entity_words for w in piece):
                continue
            if all(w in _STOPWORDS for w in piece):
                continue
            phrases.append(" ".join(piece))
    out: list[str] = []
    seen: set[str] = set()
    for p in phrases:
        p = _normalize_phrase(p)
        if p and p not in seen:
            out.append(p)
            seen.add(p)
    return out

def _bm25_scores(chunks: list[dict], query_tokens: list[str]) -> np.ndarray:
    if not chunks:
        return np.array([], dtype=float)
    tokenized = [_tokenize(c["text"] + " " + c["title"] + " " + c["section"]) for c in chunks]
    n = len(tokenized)
    avgdl = sum(len(t) for t in tokenized) / max(1, n)
    dfs: Counter[str] = Counter()
    for toks in tokenized:
        for term in set(toks):
            dfs[term] += 1
    k1 = 1.5
    b = 0.75
    raw = np.zeros(n, dtype=float)
    for i, toks in enumerate(tokenized):
        counts = Counter(toks)
        dl = max(1, len(toks))
        s = 0.0
        for term in query_tokens:
            tf = counts.get(term, 0)
            if tf <= 0:
                continue
            df = dfs.get(term, 0)
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * dl / max(avgdl, 1.0))
            s += idf * (tf * (k1 + 1.0) / denom)
        raw[i] = s
    mx = float(raw.max()) if len(raw) else 0.0
    return raw / mx if mx > 0 else raw


def _semantic_scores(index: dict, query: str) -> np.ndarray:
    matrix = index.get("semantic_matrix")
    vectorizer = index.get("vectorizer")
    if matrix is None or vectorizer is None:
        return np.zeros(len(index.get("chunks", [])), dtype=float)
    q = vectorizer.transform([query])
    svd = index.get("svd")
    if svd is not None:
        qv = normalize(svd.transform(q))
        sims = np.asarray(matrix @ qv[0]).reshape(-1)
    else:
        qv = normalize(q).toarray()[0]
        sims = np.asarray(matrix @ qv).reshape(-1)
    return np.clip(sims, 0.0, 1.0)


def _phrase_score_for_chunk(chunk: dict, phrases: list[str], phrase_df: dict[str, int], total_chunks: int) -> tuple[float, tuple[str, ...]]:
    hay = f"{chunk['title']} {chunk['section']} {chunk['text']}".lower()
    hits: list[tuple[str, float]] = []
    for p in phrases:
        if p not in hay:
            continue
        words = p.split()
        rarity = math.log((total_chunks + 1) / (phrase_df.get(p, 0) + 1)) + 1.0
        length_weight = min(2.0, 0.75 + 0.45 * len(words))
        title_boost = 1.45 if p in chunk["title"].lower() else 1.0
        hits.append((p, rarity * length_weight * title_boost))
    if not hits:
        return 0.0, ()
    hits.sort(key=lambda x: x[1], reverse=True)
    # Saturate so one strong named phrase dominates generic overlap.
    raw = sum(v for _, v in hits[:3])
    score = 1.0 - math.exp(-raw / 4.0)
    return min(1.0, score), tuple(p for p, _ in hits[:5])


def _link_anchor_score(chunk: dict, query_tokens: set[str], phrases: list[str]) -> float:
    anchors = " ".join(a for a, _ in chunk.get("external_links", ())).lower()
    if not anchors:
        return 0.0
    phrase_hit = any(p in anchors for p in phrases)
    overlap = len(query_tokens & set(_tokenize(anchors))) / max(1, len(query_tokens))
    return min(1.0, 0.65 * (1.0 if phrase_hit else 0.0) + 0.35 * overlap)


def _article_lookup(db_path: Path) -> dict[str, ArchiveArticle]:
    db = ArchiveDB(db_path)
    try:
        return {a.canonical_url: a for a in db.list_articles()}
    finally:
        db.close()


def _rank_links_for_memory(
    links: list[tuple[str, str]],
    *,
    entities: tuple[str, ...],
    free_terms: set[str],
    concepts: tuple[str, ...],
) -> list[tuple[str, str]]:
    """Rank already section-local links against the current retrieval intent."""
    scored: list[tuple[float, int, str, str]] = []
    for pos, (anchor, url) in enumerate(links):
        hay = f"{anchor} {url}".lower()
        score = 0.0
        if any(e in hay for e in entities):
            score += 4.0
        score += 0.65 * len(free_terms & set(_tokenize(hay)))
        concept_hits = [c for c in concepts if c in hay]
        score += sum(1.15 if len(_tokenize(c)) >= 2 else 0.65 for c in concept_hits[:4])
        if re.search(r"(?:patents?\.google|uspto|us\d{6,}|wo\d{6,}|ep\d{6,})", hay, flags=re.I):
            score += 1.25
        scored.append((score, -pos, anchor, url))
    scored.sort(reverse=True)
    return [(a, u) for _, _, a, u in scored]


def retrieve_archive_memory(
    db_path: Path,
    *,
    query: str,
    chunk_limit: int = 10,
    article_limit: int = 6,
    min_score: float = 0.12,
) -> list[ArchiveMemory]:
    """Retrieval v4: investigative, entity-aware hybrid archive retrieval."""
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    query = re.sub(r"\s+", " ", query).strip()
    entities, entity_components, free_terms = _query_plan(query)
    all_query_tokens = set(_tokenize(query))
    entity_component_set = set(entity_components)
    free_term_set = set(free_terms)
    if not all_query_tokens:
        return []

    index = _load_index(db_path)
    chunks: list[dict] = index.get("chunks", [])
    if not chunks:
        return []

    lexical_terms = list(free_terms) or [t for t in all_query_tokens if t not in _GENERIC_QUERY_TERMS]
    if not lexical_terms:
        lexical_terms = list(all_query_tokens)
    bm25 = _bm25_scores(chunks, lexical_terms)
    phrases = _query_phrases(query, entities)
    concepts = _expanded_concepts(index, entities, query)

    # Build an infrastructure signature from the archive passages that directly
    # mention the named entity. This lets a location/data article match Flock on
    # shared investigative infrastructure even when lexical/LSA similarity is low.
    seed_infra_terms: set[str] = set()
    if entities:
        for seed_chunk in chunks:
            seed_hay = f"{seed_chunk['title']} {seed_chunk['section']} {seed_chunk['text']}".lower()
            if any(e in seed_hay for e in entities):
                seed_infra_terms.update(_INFRASTRUCTURE_TERMS & set(_tokenize(seed_hay)))

    semantic_query = " ".join([query, *concepts[:12]]) if concepts else query
    semantic_enriched = _semantic_scores(index, semantic_query)
    semantic_base = _semantic_scores(index, " ".join(free_terms) if free_terms else query)
    generic_entity_terms = tuple(t for t in entity_components if t in _GENERIC_QUERY_TERMS)
    generic_baseline_query = " ".join([*free_terms, *generic_entity_terms]).strip()
    generic_semantic = (
        _semantic_scores(index, generic_baseline_query)
        if entities and generic_baseline_query
        else np.zeros(len(chunks), dtype=float)
    )

    total_chunks = len(chunks)
    phrase_df = {
        p: sum(1 for c in chunks if p in f"{c['title']} {c['section']} {c['text']}".lower())
        for p in phrases
    }

    scored_chunks: list[dict] = []
    for i, chunk in enumerate(chunks):
        hay = f"{chunk['title']} {chunk['section']} {chunk['text']}".lower()
        chunk_tokens = set(_tokenize(hay))
        exact_entities = tuple(e for e in entities if e in hay)
        direct_entity = bool(exact_entities)
        phrase_score, phrase_hits = _phrase_score_for_chunk(chunk, phrases, phrase_df, total_chunks)
        concept_score, concept_hits, cooccurrence = _concept_score_for_chunk(chunk, concepts)
        title_tokens = set(_tokenize(chunk["title"] + " " + chunk["section"]))
        title_basis = free_term_set or all_query_tokens
        title_overlap = len(title_basis & title_tokens) / max(1, len(title_basis))
        anchor_score = _link_anchor_score(chunk, free_term_set or all_query_tokens, phrases)

        raw_enriched = float(semantic_enriched[i]) if i < len(semantic_enriched) else 0.0
        raw_base = float(semantic_base[i]) if i < len(semantic_base) else 0.0
        baseline = float(generic_semantic[i]) if i < len(generic_semantic) else 0.0
        contrast_sem = raw_enriched if direct_entity else max(0.0, raw_enriched - 0.70 * baseline)
        sem = contrast_sem if direct_entity else max(contrast_sem, 0.72 * raw_base)
        lex = float(bm25[i]) if i < len(bm25) else 0.0
        free_overlap = bool(free_term_set & chunk_tokens) if free_term_set else False
        infra_hits = tuple(sorted(_INFRASTRUCTURE_TERMS & chunk_tokens))
        infra_pair_score = min(1.0, len(infra_hits) / 4.0)
        shared_infra = tuple(sorted(set(infra_hits) & seed_infra_terms))
        seed_infra_score = min(1.0, len(shared_infra) / 4.0)
        has_specific_phrase = any(len(_tokenize(h)) >= 2 for h in concept_hits)

        if direct_entity:
            connection_type = "direct entity match"
            connection_tier = "DIRECT"
            score = (
                0.24 * lex
                + 0.18 * sem
                + 0.24 * phrase_score
                + 0.12 * concept_score
                + 0.07 * cooccurrence
                + 0.03 * title_overlap
                + 0.02 * anchor_score
                + 0.18
            )
            score += 0.07
        else:
            # Investigative gate: one generic shared term is not a relationship.
            # Related infrastructure requires multiple concepts in the same chunk,
            # or a specific multi-word concept plus supporting infrastructure.
            related_infrastructure = (
                (cooccurrence >= 0.50 and concept_score >= 0.35)
                or (has_specific_phrase and concept_score >= 0.35 and infra_pair_score >= 0.50)
                or (len(concept_hits) >= 2 and infra_pair_score >= 0.50 and sem >= 0.12)
                or (seed_infra_score >= 0.75 and len(shared_infra) >= 3)
            )
            historical_pattern = (
                free_overlap
                and infra_pair_score >= 0.50
                and (sem >= 0.16 or concept_score >= 0.18 or seed_infra_score >= 0.50)
            ) or (
                sem >= 0.34 and infra_pair_score >= 0.50 and concept_score >= 0.18
            ) or (
                seed_infra_score >= 0.50 and len(shared_infra) >= 2 and (free_overlap or sem >= 0.10)
            )

            if related_infrastructure:
                connection_type = "strong conceptual connection"
                connection_tier = "RELATED INFRASTRUCTURE"
                score = (
                    0.18 * lex
                    + 0.23 * sem
                    + 0.27 * concept_score
                    + 0.14 * cooccurrence
                    + 0.09 * infra_pair_score
                    + 0.05 * title_overlap
                    + 0.04 * anchor_score
                    + 0.06
                )
            elif historical_pattern:
                connection_type = "background connection"
                connection_tier = "HISTORICAL / CONCEPTUAL PRECEDENT"
                score = (
                    0.20 * lex
                    + 0.30 * sem
                    + 0.17 * concept_score
                    + 0.10 * cooccurrence
                    + 0.12 * infra_pair_score
                    + 0.06 * title_overlap
                    + 0.05 * anchor_score
                )
            else:
                continue

        score = min(1.0, max(0.0, score))
        match_terms = set(free_term_set or all_query_tokens)
        if direct_entity:
            match_terms.update(t for t in entity_component_set if t not in _GENERIC_QUERY_TERMS)
        matched = tuple(sorted(match_terms & chunk_tokens))
        if score <= 0:
            continue

        scored_chunks.append({
            "idx": i,
            "chunk": chunk,
            "score": score,
            "lex": lex,
            "sem": sem,
            "phrase": phrase_score,
            "phrases": tuple(dict.fromkeys(exact_entities + phrase_hits)),
            "matched": matched,
            "concept": concept_score,
            "concept_hits": concept_hits,
            "cooccurrence": cooccurrence,
            "infra_pair": infra_pair_score,
            "shared_infra": shared_infra,
            "seed_infra": seed_infra_score,
            "connection_type": connection_type,
            "connection_tier": connection_tier,
            "direct_entity": direct_entity,
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    candidate_chunks = scored_chunks[:max(chunk_limit * 10, article_limit * 10, 50)] if chunk_limit > 0 else scored_chunks

    by_article: dict[str, list[dict]] = defaultdict(list)
    for row in candidate_chunks:
        by_article[row["chunk"]["article_url"]].append(row)

    article_map = _article_lookup(db_path)
    normalized_article_map = {_canonical_internal_url(url): a for url, a in article_map.items()}
    memories: list[ArchiveMemory] = []
    for url, rows in by_article.items():
        article = article_map.get(url)
        if article is None:
            continue
        rows.sort(key=lambda x: x["score"], reverse=True)
        top = rows[:3]
        weights = (0.80, 0.14, 0.06)
        agg = sum(r["score"] * weights[i] for i, r in enumerate(top))

        best = top[0]
        chunk = best["chunk"]
        preview_penalty = 1.0
        if article.content_status == "preview_only":
            preview_penalty = 0.88 if best["direct_entity"] else 0.68
            agg *= preview_penalty

        ranked_external = _rank_links_for_memory(
            list(chunk.get("external_links", ())),
            entities=entities,
            free_terms=free_term_set,
            concepts=concepts,
        )
        external = [
            {"anchor": a, "url": u, "type": "external_research"}
            for a, u in ranked_external
            if not _is_junk_anchor(a)
        ]

        internal_candidates: list[tuple[str, str, ArchiveArticle]] = []
        seen_internal: set[str] = set()
        for original_anchor, raw_url in chunk.get("internal_links", ()):
            if _is_junk_anchor(original_anchor):
                continue
            normalized_url = _canonical_internal_url(raw_url)
            target = normalized_article_map.get(normalized_url)
            if target is None or target.canonical_url == article.canonical_url:
                continue
            if target.canonical_url in seen_internal:
                continue
            seen_internal.add(target.canonical_url)
            internal_candidates.append((original_anchor, target.canonical_url, target))

        ranked_internal_pairs = _rank_links_for_memory(
            [(target.title, target.canonical_url) for _, _, target in internal_candidates],
            entities=entities,
            free_terms=free_term_set,
            concepts=concepts,
        )
        internal_rank = {url: i for i, (_, url) in enumerate(ranked_internal_pairs)}
        internal_candidates.sort(key=lambda x: internal_rank.get(x[1], 999))
        internal = [{
            "anchor": target.title,
            "original_anchor": original_anchor,
            "title": target.title,
            "wr_id": target.wr_id,
            "url": target.canonical_url,
            "type": "internal_article",
        } for original_anchor, _, target in internal_candidates]

        research_source_count = len(external)
        if research_source_count:
            agg += min(0.025, math.log1p(research_source_count) / 140.0)
        agg = min(1.0, agg)
        if agg < min_score:
            continue

        all_matched: set[str] = set()
        all_phrases: list[str] = []
        all_concepts: list[str] = []
        for r in top:
            all_matched.update(r["matched"])
            for p in r["phrases"]:
                if p not in all_phrases:
                    all_phrases.append(p)
            for c in r["concept_hits"]:
                if c not in all_concepts:
                    all_concepts.append(c)

        excerpt = re.sub(r"\s+", " ", chunk["text"]).strip()
        if len(excerpt) > 1400:
            excerpt = excerpt[:1397].rstrip() + "…"

        memories.append(ArchiveMemory(
            article=article,
            excerpt=excerpt,
            score=agg,
            links=external + internal,
            matched_terms=tuple(sorted(all_matched)),
            exact_phrases=tuple(all_phrases[:6]),
            semantic_score=float(best["sem"]),
            lexical_score=float(best["lex"]),
            phrase_score=float(best["phrase"]),
            best_section=chunk.get("section", ""),
            research_source_count=research_source_count,
            internal_link_count=len(internal),
            connection_type=best["connection_type"],
            query_entities=entities,
            expanded_concepts=concepts,
            concept_score=float(best["concept"]),
            concept_hits=tuple(all_concepts[:10]),
            cooccurrence_score=float(best["cooccurrence"]),
            connection_tier=best["connection_tier"],
            preview_penalty=preview_penalty,
            shared_infrastructure=tuple(best.get("shared_infra", ())),
        ))

    memories.sort(key=lambda m: (m.score, m.article.published_date or ""), reverse=True)
    return memories[:article_limit]


def format_archive_memory(memories: list[ArchiveMemory], *, max_source_links_per_article: int = 15) -> str:
    if not memories:
        return "(No sufficiently relevant previous White Rabbit articles were found.)"
    out = [
        "# PREVIOUS WHITE RABBIT ARTICLES — INSTITUTIONAL MEMORY\n",
        "These are prior published White Rabbit articles and previously used source links. "
        "Treat them as research leads, prior editorial context, style/internal-link candidates, "
        "and pointers to original sources. DO NOT treat a prior White Rabbit assertion as proof "
        "of a factual claim in the new article. Re-verify material through original sources.\n\n",
    ]
    for memory in memories:
        a = memory.article
        out.append(f"## {a.wr_id} — {a.title}\n")
        out.append(f"Relevance: {memory.score:.0%}\n")
        if memory.exact_phrases:
            out.append(f"Exact phrase/entity matches: {', '.join(memory.exact_phrases)}\n")
        if memory.matched_terms:
            out.append(f"Matched terms: {', '.join(memory.matched_terms)}\n")
        out.append(f"Connection tier: {memory.connection_tier}\n")
        out.append(f"Connection: {memory.connection_type}\n")
        if memory.query_entities:
            out.append(f"Primary query entities: {', '.join(memory.query_entities)}\n")
        if memory.expanded_concepts:
            out.append(f"Archive-derived related concepts: {', '.join(memory.expanded_concepts[:10])}\n")
        out.append(
            f"Signals: lexical={memory.lexical_score:.0%}; semantic={memory.semantic_score:.0%}; "
            f"phrase/entity={memory.phrase_score:.0%}; concept={memory.concept_score:.0%}; "
            f"co-occurrence={memory.cooccurrence_score:.0%}; "
            f"section-local external links={memory.research_source_count}\n"
        )
        if memory.concept_hits:
            out.append(f"Concepts found in best match: {', '.join(memory.concept_hits)}\n")
        if memory.shared_infrastructure:
            out.append(f"Shared infrastructure signals: {', '.join(memory.shared_infrastructure)}\n")
        if memory.preview_penalty < 1.0:
            out.append(f"Preview-only relevance multiplier: {memory.preview_penalty:.0%}\n")
        if memory.best_section:
            out.append(f"Best matching section: {memory.best_section}\n")
        out.append(f"Published article: {a.canonical_url}\n")
        if a.published_date:
            out.append(f"Published date: {a.published_date}\n")
        out.append(f"Archive content status: {a.content_status}\n")
        out.append(f"Relevant excerpt:\n{memory.excerpt}\n\n")
        links = [l for l in memory.links if l.get("type") == "external_research"][:max_source_links_per_article]
        if links:
            out.append("Section-local external sources (re-open and verify before treating as evidence):\n")
            for link in links:
                out.append(f"- {link.get('anchor', '')} → {link.get('url', '')}\n")
            out.append("\n")
        internal = [l for l in memory.links if l.get("type") == "internal_article"][:5]
        if internal:
            out.append("Prior White Rabbit internal-link candidates:\n")
            for link in internal:
                out.append(f"- {link.get('anchor', '')} → {link.get('url', '')}\n")
            out.append("\n")
    return "".join(out)
