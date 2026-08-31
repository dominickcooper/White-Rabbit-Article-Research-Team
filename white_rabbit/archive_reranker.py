from __future__ import annotations

from dataclasses import dataclass

from .archive_retrieval import ArchiveMemory
from .schemas import ArchiveRelevanceBatch, ArchiveRelevanceJudgment


@dataclass(frozen=True)
class RerankedArchiveMemory:
    memory: ArchiveMemory
    judgment: ArchiveRelevanceJudgment
    included: bool
    inclusion_reason: str


def format_candidates_for_rerank(
    memories: list[ArchiveMemory],
    *,
    max_source_links_per_article: int = 6,
    max_excerpt_chars: int = 2600,
) -> str:
    """Compact candidate packet for a single Gemini relevance-judgment call."""
    if not memories:
        return "(No archive candidates.)"

    out: list[str] = []
    for idx, memory in enumerate(memories, start=1):
        article = memory.article
        out.append(f"## Candidate {idx}: {article.wr_id} — {article.title}\n")
        out.append(f"Published URL: {article.canonical_url}\n")
        out.append(f"Local relevance: {memory.score:.0%}\n")
        out.append(f"Local connection tier: {memory.connection_tier}\n")
        out.append(f"Local connection: {memory.connection_type}\n")
        if memory.query_entities:
            out.append(f"Primary query entity/entities: {', '.join(memory.query_entities)}\n")
        if memory.exact_phrases:
            out.append(f"Exact entity/phrase match: {', '.join(memory.exact_phrases)}\n")
        if memory.best_section:
            out.append(f"Best section: {memory.best_section}\n")
        if memory.shared_infrastructure:
            out.append(f"Shared infrastructure signals: {', '.join(memory.shared_infrastructure)}\n")
        if memory.concept_hits:
            out.append(f"Concept hits: {', '.join(memory.concept_hits[:10])}\n")
        out.append(f"Content status: {article.content_status}\n")
        excerpt = (memory.excerpt or "").strip()
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[:max_excerpt_chars].rstrip() + "…"
        out.append(f"Relevant excerpt:\n{excerpt}\n")

        links = [l for l in memory.links if l.get("type") == "external_research"][:max_source_links_per_article]
        if links:
            out.append("Section-local source links available to reopen:\n")
            for link in links:
                anchor = str(link.get("anchor", "")).strip() or "(no anchor)"
                out.append(f"- {anchor} → {link.get('url', '')}\n")
        out.append("\n")
    return "".join(out)


def apply_archive_rerank(
    memories: list[ArchiveMemory],
    batch: ArchiveRelevanceBatch,
    *,
    min_score: int = 4,
    direct_matches_always_include: bool = True,
) -> list[RerankedArchiveMemory]:
    """Apply Gemini judgments while preserving obvious deterministic direct matches."""
    by_id = {j.wr_id: j for j in batch.judgments}
    results: list[RerankedArchiveMemory] = []

    for memory in memories:
        wr_id = memory.article.wr_id
        judgment = by_id.get(wr_id)
        if judgment is None:
            judgment = ArchiveRelevanceJudgment(
                wr_id=wr_id,
                score=1,
                reason="Gemini did not return a judgment for this candidate.",
                relationship="unjudged",
            )

        direct = memory.connection_tier == "DIRECT" or bool(memory.exact_phrases)
        if direct_matches_always_include and direct:
            included = True
            inclusion_reason = "direct archive entity/phrase match retained automatically"
        else:
            included = judgment.score >= min_score
            inclusion_reason = (
                f"Gemini relevance {judgment.score}/5 met threshold {min_score}/5"
                if included
                else f"Gemini relevance {judgment.score}/5 below threshold {min_score}/5"
            )
        results.append(RerankedArchiveMemory(memory, judgment, included, inclusion_reason))

    # Preserve local order within each relevance score; high Gemini scores lead.
    results.sort(
        key=lambda r: (
            1 if r.included else 0,
            r.judgment.score,
            r.memory.score,
        ),
        reverse=True,
    )
    return results


def format_curated_archive_memory(results: list[RerankedArchiveMemory]) -> str:
    included = [r for r in results if r.included]
    if not included:
        return "(Gemini found no prior White Rabbit articles materially relevant enough to use.)"

    out = [
        "# GEMINI-CURATED PREVIOUS WHITE RABBIT MEMORY\n\n",
        "These prior articles survived a separate relevance-judgment pass. They are research leads, "
        "source-reopening aids, style/internal-link candidates, and institutional memory — NOT factual proof. "
        "Re-verify claims through original sources before treating them as evidence.\n\n",
    ]
    for result in included:
        memory = result.memory
        article = memory.article
        j = result.judgment
        out.append(f"## {article.wr_id} — {article.title}\n")
        out.append(f"Gemini relevance: {j.score}/5\n")
        out.append(f"Why relevant: {j.reason}\n")
        if j.relationship:
            out.append(f"Relationship: {j.relationship}\n")
        out.append(f"Local connection tier: {memory.connection_tier}\n")
        out.append(f"Published article: {article.canonical_url}\n")
        if memory.best_section:
            out.append(f"Best matching section: {memory.best_section}\n")
        out.append(f"Relevant excerpt:\n{memory.excerpt}\n\n")
        if j.research_leads:
            out.append("Gemini-suggested research leads from this prior article:\n")
            for lead in j.research_leads[:5]:
                out.append(f"- {lead}\n")
            out.append("\n")

        external = [l for l in memory.links if l.get("type") == "external_research"]
        if j.source_urls_to_reopen:
            wanted = set(j.source_urls_to_reopen)
            selected = [l for l in external if l.get("url") in wanted]
            # Do not let a hallucinated URL erase real section-local sources.
            external = selected or external
        if external:
            out.append("Original/section-local sources to reopen and independently verify:\n")
            for link in external[:8]:
                out.append(f"- {link.get('anchor', '')} → {link.get('url', '')}\n")
            out.append("\n")

        internal = [l for l in memory.links if l.get("type") == "internal_article"][:5]
        if internal:
            out.append("Internal White Rabbit link candidates:\n")
            for link in internal:
                out.append(f"- {link.get('anchor', '')} → {link.get('url', '')}\n")
            out.append("\n")
    return "".join(out)


def rerank_audit_payload(results: list[RerankedArchiveMemory]) -> list[dict]:
    payload: list[dict] = []
    for result in results:
        memory = result.memory
        j = result.judgment
        payload.append({
            "wr_id": memory.article.wr_id,
            "title": memory.article.title,
            "url": memory.article.canonical_url,
            "local_score": round(memory.score, 4),
            "local_connection_tier": memory.connection_tier,
            "gemini_score": j.score,
            "gemini_reason": j.reason,
            "relationship": j.relationship,
            "research_leads": list(j.research_leads),
            "source_urls_to_reopen": list(j.source_urls_to_reopen),
            "included": result.included,
            "inclusion_reason": result.inclusion_reason,
        })
    return payload
