from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .archive_db import ArchiveDB, ArchiveArticle

INDEX_VERSION = 2
_INDEX_FILENAME = "archive_search_index_v2.joblib"

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


def classify_link(url: str, canonical_article_url: str) -> str:
    """Classify an archived hyperlink for retrieval use.

    external_research: candidate original source to reopen/verify
    internal_article: another White Rabbit /p/ article (internal-link candidate)
    ignored: Substack chrome, sections, profiles, media/CDN, subscribe/account links
    """
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
    for m in re.finditer(r"\[([^\]]{1,300})\]\((https?://[^)\s]+)\)", markdown):
        anchor = re.sub(r"\s+", " ", m.group(1)).strip()
        url = m.group(2).strip()
        if not anchor or not url:
            continue
        kind = classify_link(url, canonical_article_url)
        key = (anchor.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        if kind == "external_research":
            external.append((anchor, url))
        elif kind == "internal_article":
            internal.append((anchor, url))
    return external, internal


def _section_chunks(markdown: str, article: ArchiveArticle, registered_links: list[dict] | None = None, target_words: int = 650, overlap_words: int = 90) -> list[IndexedChunk]:
    clean = clean_article_markdown(markdown, article.title)
    if not clean:
        return []

    # Parse the raw Markdown too so we can preserve the links attached to each article.
    external_links, internal_links = _extract_markdown_links(markdown, article.canonical_url)
    seen_links = {(a.lower(), u) for a, u in external_links + internal_links}
    for link in registered_links or []:
        anchor = re.sub(r"\s+", " ", str(link.get("anchor", ""))).strip()
        url = str(link.get("url", "")).strip()
        if not anchor or not url or (anchor.lower(), url) in seen_links:
            continue
        kind = classify_link(url, article.canonical_url)
        if kind == "external_research":
            external_links.append((anchor, url))
            seen_links.add((anchor.lower(), url))
        elif kind == "internal_article":
            internal_links.append((anchor, url))
            seen_links.add((anchor.lower(), url))

    sections: list[tuple[str, str]] = []
    current_heading = article.title
    buf: list[str] = []
    for line in clean.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if heading:
            if buf:
                sections.append((current_heading, "\n".join(buf).strip()))
                buf = []
            current_heading = heading.group(1).strip()
            continue
        buf.append(line)
    if buf:
        sections.append((current_heading, "\n".join(buf).strip()))

    result: list[IndexedChunk] = []
    for section, body in sections:
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        words = body.split()
        if len(words) <= target_words:
            pieces = [body]
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
            result.append(IndexedChunk(
                article_url=article.canonical_url,
                wr_id=article.wr_id,
                title=article.title,
                published_date=article.published_date,
                content_status=article.content_status,
                section=section,
                text=piece,
                token_count=len(_tokenize(piece)),
                external_links=tuple(external_links),
                internal_links=tuple(internal_links),
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
            ngram_range=(1, 2),
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


def _query_phrases(query: str) -> list[str]:
    raw_words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.&'-]*", query)]
    phrases: list[str] = []
    for n in (4, 3, 2):
        for i in range(0, len(raw_words) - n + 1):
            piece = raw_words[i:i + n]
            if all(w in _STOPWORDS for w in piece):
                continue
            phrases.append(" ".join(piece))
    # Longer phrases first, no duplicates.
    out: list[str] = []
    seen: set[str] = set()
    for p in phrases:
        if p not in seen:
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


def retrieve_archive_memory(
    db_path: Path,
    *,
    query: str,
    chunk_limit: int = 10,
    article_limit: int = 6,
    min_score: float = 0.12,
) -> list[ArchiveMemory]:
    """Chunk-level hybrid retrieval across the previous White Rabbit archive.

    Components:
      * BM25 lexical relevance with inverse-document weighting
      * rare exact multi-word phrase/entity boosts
      * local latent-semantic vectors (TF-IDF -> truncated SVD), no API calls
      * title/section boosts
      * prior external-source anchor overlap

    Prior White Rabbit articles remain institutional memory / leads, never proof.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    query = re.sub(r"\s+", " ", query).strip()
    query_tokens_list = _tokenize(query)
    query_tokens = set(query_tokens_list)
    if not query_tokens:
        return []

    index = _load_index(db_path)
    chunks: list[dict] = index.get("chunks", [])
    if not chunks:
        return []

    bm25 = _bm25_scores(chunks, query_tokens_list)
    semantic = _semantic_scores(index, query)
    phrases = _query_phrases(query)
    total_chunks = len(chunks)
    phrase_df = {
        p: sum(1 for c in chunks if p in f"{c['title']} {c['section']} {c['text']}".lower())
        for p in phrases
    }

    scored_chunks: list[dict] = []
    for i, chunk in enumerate(chunks):
        phrase_score, phrase_hits = _phrase_score_for_chunk(chunk, phrases, phrase_df, total_chunks)
        title_tokens = set(_tokenize(chunk["title"] + " " + chunk["section"]))
        title_overlap = len(query_tokens & title_tokens) / max(1, len(query_tokens))
        anchor_score = _link_anchor_score(chunk, query_tokens, phrases)
        sem = float(semantic[i]) if i < len(semantic) else 0.0
        lex = float(bm25[i]) if i < len(bm25) else 0.0

        # Exact rare phrases/entities should dominate generic words like "safety".
        score = (
            0.36 * lex
            + 0.24 * sem
            + 0.24 * phrase_score
            + 0.10 * title_overlap
            + 0.06 * anchor_score
        )
        if phrase_hits and any(len(p.split()) >= 2 for p in phrase_hits):
            score += 0.08
        score = min(1.0, score)

        matched = tuple(sorted(query_tokens & set(_tokenize(chunk["title"] + " " + chunk["section"] + " " + chunk["text"]))))
        if score <= 0 or not matched:
            # Semantic-only matches are permitted only when the semantic signal is strong.
            if sem < 0.28:
                continue
        scored_chunks.append({
            "idx": i,
            "chunk": chunk,
            "score": score,
            "lex": lex,
            "sem": sem,
            "phrase": phrase_score,
            "phrases": phrase_hits,
            "matched": matched,
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    if chunk_limit > 0:
        # Keep more than the display chunk limit to allow article aggregation.
        candidate_chunks = scored_chunks[:max(chunk_limit * 8, article_limit * 8, 40)]
    else:
        candidate_chunks = scored_chunks

    by_article: dict[str, list[dict]] = defaultdict(list)
    for row in candidate_chunks:
        by_article[row["chunk"]["article_url"]].append(row)

    article_map = _article_lookup(db_path)
    memories: list[ArchiveMemory] = []
    for url, rows in by_article.items():
        article = article_map.get(url)
        if article is None:
            continue
        rows.sort(key=lambda x: x["score"], reverse=True)
        top = rows[:3]
        weights = (0.78, 0.15, 0.07)
        agg = sum(r["score"] * weights[i] for i, r in enumerate(top))

        best = top[0]
        chunk = best["chunk"]
        external = [{"anchor": a, "url": u, "type": "external_research"} for a, u in chunk.get("external_links", ())]
        internal = [{"anchor": a, "url": u, "type": "internal_article"} for a, u in chunk.get("internal_links", ())]
        research_source_count = len(external)
        if research_source_count:
            agg += min(0.04, math.log1p(research_source_count) / 100.0)
        agg = min(1.0, agg)
        if agg < min_score:
            continue

        all_matched: set[str] = set()
        all_phrases: list[str] = []
        for r in top:
            all_matched.update(r["matched"])
            for p in r["phrases"]:
                if p not in all_phrases:
                    all_phrases.append(p)

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
        out.append(
            f"Signals: lexical={memory.lexical_score:.0%}; semantic={memory.semantic_score:.0%}; "
            f"phrase/entity={memory.phrase_score:.0%}; external research links={memory.research_source_count}\n"
        )
        if memory.best_section:
            out.append(f"Best matching section: {memory.best_section}\n")
        out.append(f"Published article: {a.canonical_url}\n")
        if a.published_date:
            out.append(f"Published date: {a.published_date}\n")
        out.append(f"Archive content status: {a.content_status}\n")
        out.append(f"Relevant excerpt:\n{memory.excerpt}\n\n")
        links = [l for l in memory.links if l.get("type") == "external_research"][:max_source_links_per_article]
        if links:
            out.append("Previously used external sources (re-open and verify before treating as evidence):\n")
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
