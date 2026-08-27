from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .archive_db import ArchiveDB, ArchiveArticle
from .local_sources import LocalDocument, TextChunk, chunk_document


_STOPWORDS = {
    "about", "after", "again", "against", "also", "among", "and", "are", "because",
    "been", "before", "being", "between", "both", "but", "can", "could", "did", "does",
    "from", "had", "has", "have", "how", "into", "its", "more", "most", "not", "of",
    "off", "on", "or", "our", "over", "should", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "under", "was",
    "were", "what", "when", "where", "which", "while", "who", "why", "will", "with",
    "would", "you", "your",
}


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text)
        if token.lower() not in _STOPWORDS
    ]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


@dataclass(frozen=True)
class ArchiveMemory:
    article: ArchiveArticle
    excerpt: str
    score: float
    links: list[dict]
    matched_terms: tuple[str, ...] = ()


def _load_article_document(article: ArchiveArticle) -> LocalDocument | None:
    path = Path(article.local_dir) / "article.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    return LocalDocument(path=path.resolve(), title=article.title, text=text)


def _best_excerpt(text: str, query_tokens: set[str], max_chars: int = 1400) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    lowered = cleaned.lower()
    positions = [lowered.find(token) for token in query_tokens]
    positions = [p for p in positions if p >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - max_chars // 4)
    end = min(len(cleaned), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)
    excerpt = cleaned[start:end].strip()
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(cleaned):
        excerpt += "…"
    return excerpt


def retrieve_archive_memory(
    db_path: Path,
    *,
    query: str,
    chunk_limit: int = 10,
    article_limit: int = 6,
) -> list[ArchiveMemory]:
    """Retrieve prior White Rabbit articles with hybrid local ranking.

    Ranking intentionally requires no external API call. It combines:
    - inverse-document-frequency weighted query terms in article text
    - title term/phrase boosts
    - body phrase and query-bigram boosts
    - previously used hyperlink-anchor matches

    Prior articles remain institutional memory / research leads, never automatic
    evidence for a new article.
    """
    if not Path(db_path).exists():
        return []

    query_text = re.sub(r"\s+", " ", query).strip().lower()
    query_list = _tokens(query)
    query_terms = set(query_list)
    if not query_terms:
        return []
    query_bigrams = _bigrams(query_list)

    db = ArchiveDB(db_path)
    try:
        records: list[tuple[ArchiveArticle, LocalDocument, list[dict], Counter[str], set[tuple[str, str]]]] = []
        document_frequency: Counter[str] = Counter()

        for article in db.list_articles():
            doc = _load_article_document(article)
            if not doc:
                continue
            links = db.links_for(article.canonical_url)
            body_tokens = _tokens(doc.text)
            counts = Counter(body_tokens)
            present = query_terms & set(counts)
            for term in present:
                document_frequency[term] += 1
            records.append((article, doc, links, counts, _bigrams(body_tokens)))

        total_docs = max(1, len(records))
        idf = {
            term: math.log((total_docs + 1) / (document_frequency.get(term, 0) + 1)) + 1.0
            for term in query_terms
        }
        max_idf_sum = sum(idf.values()) or 1.0

        ranked: list[ArchiveMemory] = []
        for article, doc, links, counts, body_bigrams in records:
            title_lower = article.title.lower()
            body_lower = doc.text.lower()
            title_terms = set(_tokens(article.title))
            anchor_text = " ".join(str(link.get("anchor", "")) for link in links)
            anchor_terms = set(_tokens(anchor_text))

            # Saturated TF-IDF term relevance.
            term_score = sum(
                idf[t] * min(1.0, counts.get(t, 0) / 2.0)
                for t in query_terms
            ) / max_idf_sum

            title_overlap = len(query_terms & title_terms) / max(1, len(query_terms))
            anchor_overlap = len(query_terms & anchor_terms) / max(1, len(query_terms))

            if query_bigrams:
                bigram_overlap = len(query_bigrams & body_bigrams) / len(query_bigrams)
            else:
                bigram_overlap = 0.0

            exact_title = 1.0 if query_text and query_text in title_lower else 0.0
            exact_body = 1.0 if query_text and query_text in body_lower else 0.0

            # Weighted hybrid score. Keep it bounded for readable percentages.
            score = (
                0.48 * term_score
                + 0.24 * title_overlap
                + 0.10 * anchor_overlap
                + 0.08 * bigram_overlap
                + 0.06 * exact_title
                + 0.04 * exact_body
            )
            score = max(0.0, min(1.0, score))

            matched = tuple(sorted(query_terms & (set(counts) | title_terms | anchor_terms)))
            if not matched:
                continue

            excerpt = _best_excerpt(doc.text, query_terms)
            ranked.append(
                ArchiveMemory(
                    article=article,
                    excerpt=excerpt,
                    score=score,
                    links=links,
                    matched_terms=matched,
                )
            )

        ranked.sort(key=lambda m: (m.score, m.article.published_date or ""), reverse=True)
        return ranked[:article_limit]
    finally:
        db.close()


def format_archive_memory(memories: list[ArchiveMemory], *, max_source_links_per_article: int = 15) -> str:
    if not memories:
        return "(No relevant previous White Rabbit articles were found.)"
    out = [
        "# PREVIOUS WHITE RABBIT ARTICLES — INSTITUTIONAL MEMORY\n",
        "These are prior published White Rabbit articles and their previously used links. "
        "Treat them as research leads, prior editorial context, style/internal-link candidates, "
        "and pointers to original sources. DO NOT treat a prior White Rabbit assertion as proof "
        "of a factual claim in the new article. Re-verify material through original sources.\n\n",
    ]
    for memory in memories:
        a = memory.article
        out.append(f"## {a.wr_id} — {a.title}\n")
        out.append(f"Relevance: {memory.score:.0%}\n")
        if memory.matched_terms:
            out.append(f"Matched terms: {', '.join(memory.matched_terms)}\n")
        out.append(f"Published article: {a.canonical_url}\n")
        if a.published_date:
            out.append(f"Published date: {a.published_date}\n")
        out.append(f"Archive content status: {a.content_status}\n")
        out.append(f"Relevant excerpt:\n{memory.excerpt}\n\n")
        links = memory.links[:max_source_links_per_article]
        if links:
            out.append("Previously used links (re-open and verify before treating as evidence):\n")
            for link in links:
                out.append(f"- {link.get('anchor', '')} → {link.get('url', '')} [{link.get('type', 'external')}]\n")
            out.append("\n")
    return "".join(out)
