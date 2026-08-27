from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .archive_db import ArchiveDB, ArchiveArticle
from .local_sources import LocalDocument, TextChunk, chunk_document, rank_chunks


@dataclass(frozen=True)
class ArchiveMemory:
    article: ArchiveArticle
    excerpt: str
    score: float
    links: list[dict]


def _load_article_document(article: ArchiveArticle) -> LocalDocument | None:
    path = Path(article.local_dir) / "article.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    return LocalDocument(path=path.resolve(), title=article.title, text=text)


def retrieve_archive_memory(
    db_path: Path,
    *,
    query: str,
    chunk_limit: int = 10,
    article_limit: int = 6,
) -> list[ArchiveMemory]:
    if not Path(db_path).exists():
        return []
    db = ArchiveDB(db_path)
    try:
        article_by_path: dict[str, ArchiveArticle] = {}
        chunks: list[TextChunk] = []
        for article in db.list_articles():
            doc = _load_article_document(article)
            if not doc:
                continue
            article_by_path[str(doc.path)] = article
            chunks.extend(chunk_document(doc, max_chars=9000, overlap=800))
        ranked = rank_chunks(chunks, query, max(chunk_limit * 3, article_limit))
        memories: list[ArchiveMemory] = []
        seen: set[str] = set()
        for chunk in ranked:
            article = article_by_path.get(str(chunk.document.path))
            if not article or article.canonical_url in seen:
                continue
            seen.add(article.canonical_url)
            excerpt = re.sub(r"\s+", " ", chunk.text).strip()[:4200]
            memories.append(
                ArchiveMemory(
                    article=article,
                    excerpt=excerpt,
                    score=chunk.score,
                    links=db.links_for(article.canonical_url),
                )
            )
            if len(memories) >= article_limit:
                break
        return memories
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
