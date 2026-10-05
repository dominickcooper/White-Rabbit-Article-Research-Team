from __future__ import annotations

import json
import re
import time
from typing import TypeVar, Type

from pydantic import BaseModel

from .json_repair import parse_structured
from .schemas import (
    AnchorMap,
    ArchiveRelevanceBatch,
    ArticleMetadata,
    ArticleOutline,
    AuditReport,
    CitationRef,
    EvidenceExtraction,
    ResearchPlan,
    SourceThesis,
    WebResearchResult,
    WriterPacket,
)

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_MARKERS = (
    "429",
    "resource_exhausted",
    "rate limit",
    "ratelimit",
    "unavailable",
    "503",
    "500",
    "timeout",
    "temporarily",
    "try again",
)

_FATAL_MARKERS = (
    "invalid argument",
    "invalid_argument",
    "permission denied",
    "unauthenticated",
    "api key",
    "not found",
)


class GeminiProvider:
    """Thin wrapper around the current Google GenAI Interactions API.

    The import is intentionally lazy so unit tests can run without google-genai installed.
    """

    def __init__(self, api_key: str, model: str = "gemini-3.7-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install google-genai: pip install google-genai") from exc
        self.genai = genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        text = str(exc).lower()
        code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if code in {429, 500, 502, 503, 504}:
            return True
        if any(marker in text for marker in _FATAL_MARKERS):
            return False
        return any(marker in text for marker in _RETRYABLE_MARKERS)

    def _retry(self, fn, attempts: int = 5):
        delay = 2.0
        last = None
        for i in range(attempts):
            try:
                return fn()
            except Exception as exc:
                last = exc
                if i == attempts - 1 or not self._is_retryable(exc):
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 32.0)
        raise last  # pragma: no cover

    @staticmethod
    def _interaction_json_schema(schema: Type[T]) -> dict:
        """Return a Gemini-compatible JSON Schema for structured outputs.

        Pydantic emits a broader JSON Schema dialect than Gemini Interactions accepts.
        In particular, string bounds such as ``maxLength``/``minLength`` and defaults
        can make the API reject an otherwise simple extraction schema with HTTP 400.
        Keep the local Pydantic constraints for post-response validation, but strip
        unsupported keywords from the schema sent to Gemini.
        """
        unsupported = {
            "maxLength", "minLength", "pattern", "default", "examples",
            "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
            "minProperties", "maxProperties", "const",
        }

        def clean(value):
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items() if k not in unsupported}
            if isinstance(value, list):
                return [clean(v) for v in value]
            return value

        return clean(schema.model_json_schema())

    def _structured(
        self,
        prompt: str,
        schema: Type[T],
        *,
        tools: list[dict] | None = None,
        max_output_tokens: int | None = None,
        thinking_level: str | None = None,
        compact_retry: bool = False,
    ) -> T:
        response_schema = self._interaction_json_schema(schema)

        def build_kwargs(current_prompt: str, token_cap: int | None, level: str | None) -> dict:
            kwargs = {
                "model": self.model,
                "input": current_prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": response_schema,
                },
            }
            if tools:
                kwargs["tools"] = tools
            generation_config: dict = {}
            if token_cap is not None:
                generation_config["max_output_tokens"] = int(token_cap)
            if level:
                generation_config["thinking_level"] = level
            if generation_config:
                kwargs["generation_config"] = generation_config
            return kwargs

        kwargs = build_kwargs(prompt, max_output_tokens, thinking_level)
        interaction = self._retry(lambda: self.client.interactions.create(**kwargs))
        try:
            return parse_structured(interaction.output_text, schema)
        except Exception:
            if not compact_retry:
                raise

        # A long source can occasionally provoke an overlong JSON object even with
        # structured output enabled. Retry once with an explicit compact instruction
        # and a smaller token budget instead of letting one source kill the run.
        repair_prompt = prompt + """

CRITICAL RETRY INSTRUCTION:
Your previous structured response was too large or malformed. Return a COMPACT valid JSON response only.
Do not summarize the whole source. Include only the strongest evidence that directly answers the research question.
Use at most 5 evidence items. Keep source_summary under 500 characters, each claim under 500 characters,
each excerpt under 500 characters, and each significance field under 400 characters.
"""
        retry_cap = min(max_output_tokens or 4096, 4096)
        retry_kwargs = build_kwargs(repair_prompt, retry_cap, "low")
        repaired = self._retry(lambda: self.client.interactions.create(**retry_kwargs), attempts=2)
        return parse_structured(repaired.output_text, schema)

    @staticmethod
    def _source_terms(text: str) -> set[str]:
        stop = {
            "about", "after", "again", "against", "article", "could", "from", "have",
            "into", "more", "question", "research", "source", "that", "their", "there",
            "these", "they", "this", "those", "through", "using", "what", "when", "where",
            "which", "with", "would", "your",
        }
        return {
            tok for tok in re.findall(r"[a-z0-9][a-z0-9_.-]{2,}", text.lower())
            if tok not in stop and not tok.isdigit()
        }

    @classmethod
    def _select_source_chunks(
        cls,
        text: str,
        query: str,
        *,
        chunk_chars: int = 18000,
        overlap: int = 1200,
        max_chunks: int = 3,
    ) -> list[str]:
        cleaned = text.replace("\x00", " ").strip()
        if len(cleaned) <= 22000:
            return [cleaned]

        step = max(2000, chunk_chars - overlap)
        windows: list[tuple[int, str]] = []
        for start in range(0, len(cleaned), step):
            chunk = cleaned[start:start + chunk_chars]
            if not chunk.strip():
                continue
            windows.append((start, chunk))
            if start + chunk_chars >= len(cleaned):
                break

        qterms = cls._source_terms(query)
        query_l = query.lower().strip()
        scored: list[tuple[float, int, str]] = []
        for start, chunk in windows:
            lower = chunk.lower()
            overlap_score = sum(min(4, lower.count(term)) for term in qterms)
            phrase_bonus = 8 if query_l and query_l in lower else 0
            # Give headings/opening metadata a small tie-breaker without forcing the
            # first chunk to win over genuinely relevant later PDF sections.
            opening_bonus = 0.5 if start == 0 else 0.0
            scored.append((overlap_score + phrase_bonus + opening_bonus, start, chunk))

        chosen = sorted(scored, key=lambda row: (-row[0], row[1]))[:max_chunks]
        # Process in source order so extracted evidence remains easy to audit.
        return [chunk for _, _, chunk in sorted(chosen, key=lambda row: row[1])]

    @staticmethod
    def _citations_from_interaction(interaction) -> list[CitationRef]:
        found: list[CitationRef] = []
        seen: set[str] = set()
        for step in getattr(interaction, "steps", []) or []:
            if getattr(step, "type", None) != "model_output":
                continue
            for block in getattr(step, "content", []) or []:
                for ann in getattr(block, "annotations", []) or []:
                    if getattr(ann, "type", None) != "url_citation":
                        continue
                    url = (getattr(ann, "url", "") or "").strip()
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    found.append(CitationRef(title=(getattr(ann, "title", "") or "").strip(), url=url))
        return found

    def doctor(self) -> str:
        interaction = self._retry(
            lambda: self.client.interactions.create(
                model=self.model,
                input="Reply with exactly: WHITE RABBIT GEMINI OK",
            )
        )
        return (interaction.output_text or "").strip()

    def derive_source_thesis(
        self, topic: str, angle: str, source_corpus: str, canon_memory: str = ""
    ) -> SourceThesis:
        prompt = f"""
You are the source-thesis researcher for The White Rabbit Report. This happens before
external research. The author selected the source corpus deliberately.

AUTHOR OBJECTIVE / TOPIC:
{topic}

OPTIONAL EXPLICIT ANGLE:
{angle or '(none supplied)'}

AUTHOR-SELECTED SOURCE CORPUS:
{source_corpus or '(no readable supplied text; preserve this limitation)'}

RELEVANT PUBLISHED WHITE RABBIT CANON (separate factual retrieval):
{canon_memory or '(none retrieved)'}

Identify the strongest coherent investigation emerging from the explicit objective and
source corpus. Do not replace it with a more conventional or easier adjacent article.
Preserve competing source claims, accepted testimony provenance, genuine contradictions,
entities, initial connection chains, predicted documentary footprints and concrete
external research objectives. Canon can become an established premise and open a next
hop; it does not override explicit author intent. Set status LOCKED unless irreducible
ambiguity genuinely requires AUTHOR THESIS DECISION REQUIRED. Do not suppress contrary
evidence and do not claim every allegation is independently proven.
"""
        return self._structured(prompt, SourceThesis)

    def plan_research(
        self, topic: str, angle: str, style: str, max_questions: int,
        publication_memory: str = "", source_thesis: str = "", canon_memory: str = "",
    ) -> ResearchPlan:
        prompt = f"""
You are the research planner for an evidence-first investigative publication.

TOPIC:
{topic}

OPTIONAL ANGLE:
{angle or '(none supplied)'}

LOCKED SOURCE THESIS:
{source_thesis or '(missing: return only questions needed to complete it)'}

PUBLISHED WHITE RABBIT CANON:
{canon_memory or publication_memory or '(none)'}

Create a research plan for ONE article. Return no more than {max_questions} high-value research questions.
The plan must deliberately cover:
- baseline facts and chronology
- major people, companies, agencies, programs, money, contracts, patents, or filings when relevant
- primary-source targets
- meaningful second-order connections
- credible conventional explanations and contrary evidence
- unresolved factual gaps

Search queries should be practical Google queries, with precise names/identifiers when possible. Treat stated facts, findings, connections and conclusions in published White Rabbit memory as Level 1 project canon: they may seed new research without automatic re-verification. Reopen an underlying source when the author requests it, canon was marked unresolved/speculative, exact wording matters, genuine contrary evidence appears, or the trail can open a new branch. Do not count canon as an independent corroborating stream or assume a new extension of the thesis is true.
Every question must develop, test, or materially challenge the locked source-derived
investigation. External research may not silently substitute a safer adjacent thesis.
"""
        return self._structured(prompt, ResearchPlan)

    def rerank_archive_memory(self, topic: str, angle: str, candidates: str) -> ArchiveRelevanceBatch:
        prompt = f"""
You are the archive relevance editor for The White Rabbit Report.

CURRENT INVESTIGATION:
{topic}

OPTIONAL ANGLE:
{angle or '(none supplied)'}

Below are candidate PREVIOUS White Rabbit articles returned by a broad local retrieval system.
The local system is intentionally high-recall and may include false positives. Your job is to judge
whether each prior article is materially useful to THIS investigation.

CANDIDATES:
{candidates}

Score EVERY candidate exactly once on this 1-5 scale:
5 = DIRECTLY RELEVANT. Same investigation/entity, or contains important evidence/connections/sources that clearly belong in the new research.
4 = STRONGLY RELEVANT. Not the same article topic, but provides a meaningful technology, infrastructure, people/company/agency, funding, historical-precedent, or source trail that is genuinely worth examining.
3 = POSSIBLY USEFUL CONTEXT. Some real contextual value, but not strong enough to automatically feed into the research plan.
2 = WEAK. Mostly superficial overlap or a generic shared theme.
1 = IRRELEVANT. Accidental keyword/semantic similarity.

STRICT RULES:
- Do NOT score highly merely because both articles mention generic words like surveillance, intelligence, safety, cameras, patents, government, roads, security, data, or technology.
- Ask: would a careful investigative reporter reasonably reopen this prior article or its source trail before researching the new topic?
- A non-obvious connection may score 4-5 when it is specific and materially useful.
- A sensational or conspiratorial similarity alone is not relevance.
- Previous published White Rabbit assertions are Level 1 project canon. Judge relevance to the next research branch; do not require re-verification before they can be used as premises.
- source_urls_to_reopen MUST contain only URLs that were explicitly supplied in that candidate's section-local source list. Do not invent URLs.
- research_leads should be concise, concrete follow-up questions or source checks, not conclusions.
- relationship should be a short label such as "direct entity overlap", "surveillance infrastructure precedent", "shared investor/company network", "historical civil-liberties precedent", or "superficial overlap".

Return structured judgments for every candidate.
"""
        return self._structured(prompt, ArchiveRelevanceBatch)

    def web_research(self, qid: str, question: str, search_query: str) -> WebResearchResult:
        prompt = f"""
Investigate this question using Google Search grounding.

QUESTION:
{question}

STARTING SEARCH QUERY:
{search_query}

Prefer primary records and official sources when they exist. Search beyond the starting query when useful.
Write concise research notes that preserve exact names, dates, identifiers, dollar amounts, program names, patent/contract numbers, and contradictions. Distinguish fact from inference. Include credible contrary information. Do not write the article.
"""
        interaction = self._retry(
            lambda: self.client.interactions.create(
                model=self.model,
                input=prompt,
                tools=[{"type": "google_search"}],
            )
        )
        return WebResearchResult(
            question_id=qid,
            question=question,
            search_query=search_query,
            notes=interaction.output_text or "",
            citations=self._citations_from_interaction(interaction),
        )

    def extract_evidence_from_text(
        self,
        *,
        topic: str,
        research_question: str,
        source_title: str,
        source_locator: str,
        text: str,
    ) -> EvidenceExtraction:
        query = f"{topic} {research_question} {source_title}"
        chunks = self._select_source_chunks(text, query)
        merged_items = []
        summaries: list[str] = []
        seen_claims: set[str] = set()
        last_error: Exception | None = None
        any_success = False

        for idx, chunk in enumerate(chunks, start=1):
            prompt = f"""
You are extracting auditable evidence for an investigative article.

ARTICLE TOPIC:
{topic}

RESEARCH QUESTION:
{research_question}

SOURCE TITLE:
{source_title}

SOURCE LOCATOR:
{source_locator}

SOURCE TEXT CHUNK {idx}/{len(chunks)}:
---
{chunk}
---

Extract only material genuinely relevant to the topic/question. Do NOT summarize the entire source.
Return at most 6 of the strongest evidence items from this chunk. For each item:
- state one narrow claim the source supports
- if possible provide a SHORT exact excerpt copied from SOURCE TEXT (do not manufacture quotations)
- identify date/author only if visible
- classify evidentiary level: documented_fact, strong_inference, plausible_connection, or speculation
- classify reliability: primary, high_quality_secondary, secondary, or unknown
- list only important entities
- explain briefly why it matters

OUTPUT BOUNDS:
- source_summary: <= 600 characters
- claim: <= 700 characters
- excerpt: <= 240 characters
- significance: <= 500 characters
- entities: <= 15

A source can be relevant while supporting only a limited claim. Do not upgrade inference into fact.
If nothing useful is present in this chunk, return relevant=false with no items.
"""
            try:
                extraction = self._structured(
                    prompt,
                    EvidenceExtraction,
                    max_output_tokens=4500,
                    thinking_level="low",
                    compact_retry=True,
                )
                any_success = True
            except Exception as exc:
                last_error = exc
                continue

            if extraction.source_summary and len(" ".join(summaries)) < 1100:
                summaries.append(extraction.source_summary.strip())
            for item in extraction.items:
                key = re.sub(r"\W+", " ", item.claim.lower()).strip()
                if not key or key in seen_claims:
                    continue
                seen_claims.add(key)
                merged_items.append(item)
                if len(merged_items) >= 12:
                    break
            if len(merged_items) >= 12:
                break

        if not any_success and last_error is not None:
            raise last_error

        summary = " ".join(summaries).strip()[:1200]
        return EvidenceExtraction(
            relevant=bool(merged_items),
            source_summary=summary,
            items=merged_items[:12],
        )

    def extract_evidence_from_url(
        self,
        *,
        topic: str,
        research_question: str,
        source_title: str,
        url: str,
    ) -> EvidenceExtraction:
        prompt = f"""
Use URL Context to inspect this source directly: {url}

ARTICLE TOPIC: {topic}
RESEARCH QUESTION: {research_question}
SOURCE TITLE: {source_title}

Extract only the strongest narrow, auditable evidence relevant to the question. Do NOT summarize the whole page/document.
Return at most 8 evidence items. If quoting, copy only a short exact excerpt. Preserve exact dates, identifiers,
amounts and names. Distinguish documented fact, inference, plausible connection and speculation.

OUTPUT BOUNDS:
- source_summary: <= 600 characters
- claim: <= 700 characters
- excerpt: <= 240 characters
- significance: <= 500 characters
- entities: <= 15

Return relevant=false if the source does not materially help.
"""
        return self._structured(
            prompt,
            EvidenceExtraction,
            tools=[{"type": "url_context"}],
            max_output_tokens=5000,
            thinking_level="low",
            compact_retry=True,
        )

    def build_outline(
        self, topic: str, angle: str, evidence_packet: str, style: str,
        publication_memory: str = "", source_thesis: str = "", canon_memory: str = "",
    ) -> ArticleOutline:
        prompt = f"""
You are outlining ONE White Rabbit Report investigative article.

TOPIC: {topic}
ANGLE: {angle or '(develop the strongest evidence-supported angle)'}

STYLE RULES:
{style}

EVIDENCE PACKET:
{evidence_packet}

LOCKED SOURCE THESIS:
{source_thesis or '(not supplied)'}

PREVIOUS WHITE RABBIT ARTICLES (Level 1 factual project canon):
{canon_memory or publication_memory or '(none)'}

Build a compelling 12–20-section structure when the record supports that many sections. Every evidence_id you assign must exist in the packet; a section relying only on a clearly identified canonical premise may use no evidence_id. Use canon briefly, then open a new branch. Include actual contrary evidence where material; do not manufacture a defensive counterargument after every finding. End sections by opening the next door. Do not invent facts to fill structural gaps.
The outline must develop the locked investigation. If the evidence requires a fundamental
change, do not substitute it here; return an outline whose thesis explicitly says AUTHOR
THESIS DECISION REQUIRED and identifies the contradiction.
"""
        return self._structured(prompt, ArticleOutline)

    def build_writer_packet(
        self, *, source_thesis: str, outline: ArticleOutline, evidence_packet: str,
        canon_memory: str = "", voice_memory: str = "",
    ) -> WriterPacket:
        prompt = f"""
Act as the showrunner. Build the controlled Writer Packet for the assigned investigation.

SOURCE THESIS:
{source_thesis}

APPROVED STORY OUTLINE:
{outline.model_dump_json(indent=2)}

COMPLETE EVIDENCE RECORD (for packet selection, not wholesale transfer):
{evidence_packet}

PUBLISHED CANON:
{canon_memory or '(none)'}

FILTERED GOLD VOICE REFERENCE:
{voice_memory or '(none)'}

Select the strongest supported findings, testimony with provenance, canon premises,
characters, five to ten consequential dependency-aware chains where available, three to
five actually investigated rabbit holes with honest dispositions, crucial documentary
details/IDs/locators, chronology, surprises, contradictions, factual boundaries, source
locators and reveal order. Voice lessons must describe behavior, not copy sentences.
Do not include abandoned research bureaucracy or invent missing discoveries.
"""
        return self._structured(prompt, WriterPacket)

    def write_article(
        self, topic: str, angle: str, outline: ArticleOutline, evidence_packet: str,
        style: str, publication_memory: str = "", source_thesis: str = "",
        writer_packet: str = "", canon_memory: str = "", voice_memory: str = "",
    ) -> str:
        prompt = f"""
Write the complete Markdown article for The White Rabbit Report.

TOPIC: {topic}
ANGLE: {angle or '(use the outline thesis)'}

STYLE RULES:
{style}

APPROVED OUTLINE:
{outline.model_dump_json(indent=2)}

LOCKED SOURCE THESIS:
{source_thesis or '(not supplied)'}

CONTROLLED WRITER PACKET:
{writer_packet or evidence_packet}

PUBLISHED WHITE RABBIT CANON:
{canon_memory or publication_memory or '(none)'}

FILTERED GOLD VOICE REFERENCE:
{voice_memory or '(none)'}

CRITICAL EVIDENCE RULES:
1. Base new factual claims on the evidence packet. Stated findings in PREVIOUS WHITE RABBIT ARTICLES are Level 1 canon and may be used as premises without re-verification.
2. Append evidence markers like [[EV-0001]] immediately after factual sentences they support.
3. Use only evidence IDs that exist in the packet.
4. Treat UNVERIFIED excerpts as paraphrase evidence only; never put them in quotation marks.
5. For direct quotations, use only VERIFIED excerpts and keep quotations short.
6. Clearly distinguish documented fact, strong inference, plausible connection, and speculation.
7. Include actual material contrary evidence and the strongest relevant conventional explanation; do not insert defensive balance after every finding.
8. Do not place external Markdown hyperlinks in the draft; the publishing pipeline will add them.
9. You MAY add 3–6 natural internal Markdown links to previous White Rabbit articles, but ONLY using exact published URLs supplied in PREVIOUS WHITE RABBIT ARTICLES. Never invent an internal URL.
10. Canon claims should use the exact supplied internal article URL and need no invented EV marker. They do not count as an independent corroborating stream. New external claims still require EV evidence markers.
11. Accepted named testimony may become a downstream premise while retaining testimonial provenance. Attribute first use where useful, then follow the people, organizations, programs, places, events or documents it names.
12. Reason cumulatively. Use corroboration to open new branches, not only to retry accepted premises. Avoid repeated “this does not prove,” “not X but Y,” “stronger conclusion,” “better question,” and section-ending thesis recaps.
13. Develop the locked source-selected investigation. Do not replace it with a safer
adjacent story. If the packet records AUTHOR THESIS DECISION REQUIRED, stop rather than
drafting an unapproved replacement.

The article body should normally be roughly 2,000–3,500 words. Include useful [IMAGE: ...] notes and five FAQs. If no internal White Rabbit links were supplied, omit rather than invent the "You May Be Interested" links.
"""
        interaction = self._retry(lambda: self.client.interactions.create(model=self.model, input=prompt))
        return (interaction.output_text or "").strip()

    def audit_article(
        self, article: str, evidence_packet: str, publication_memory: str = "",
        source_thesis: str = "", canon_memory: str = "",
    ) -> AuditReport:
        prompt = f"""
Act as an adversarial source editor. Audit this draft against the evidence packet and
published White Rabbit canon.

EVIDENCE PACKET:
{evidence_packet}

PUBLISHED WHITE RABBIT CANON:
{canon_memory or publication_memory or '(none)'}

LOCKED SOURCE THESIS:
{source_thesis or '(not supplied)'}

ARTICLE:
{article}

Flag fabrication, source-type conversion, invented relationships, claims stronger than their source, wrong evidence markers, genuine omitted contrary evidence, repetition, and thesis drift. Treat a claim actually supported by the supplied published canon as accepted without an EV marker. Also flag defensive collapse: re-proving canon, treating accepted testimony as unusable, resetting inference at each edge, or weakening cumulative inference merely for lack of a smoking gun. Do not flag rhetorical questions, clearly marked personal theory, or supported cumulative inference merely because they are not direct facts.

Return targeted findings only. Every substantive finding must provide exact locator or
excerpt, evidence IDs, required factual constraint and minimum correction. Do not rewrite
the draft and do not approve a fundamental thesis change. pass_for_publish should be false
if any blocker remains; it is an evidence-audit result, never human publication approval.
"""
        return self._structured(prompt, AuditReport)

    def revise_article(
        self, article: str, audit: AuditReport, evidence_packet: str, style: str,
        publication_memory: str = "", source_thesis: str = "", canon_memory: str = "",
        voice_memory: str = "",
    ) -> str:
        prompt = f"""
Revise the White Rabbit Report draft to resolve the audit findings without adding new unsupported claims.

STYLE RULES:
{style}

AUDIT:
{audit.model_dump_json(indent=2)}

EVIDENCE PACKET:
{evidence_packet}

PUBLISHED WHITE RABBIT CANON:
{canon_memory or publication_memory or '(none)'}

LOCKED SOURCE THESIS:
{source_thesis or '(not supplied)'}

FILTERED GOLD VOICE REFERENCE:
{voice_memory or '(none)'}

DRAFT:
{article}

Apply only the targeted minimum corrections. Preserve valid evidence markers and exact supplied canon links. Correct unsupported material
without reflexively weakening accepted testimony, canon, or a supported cumulative
inference. Remove defensive AI-tic phrasing rather than replacing it with a new stock
caveat. Do not perform a broad rewrite, flatten the narrator, or change the locked thesis.
Return only the complete revised Markdown article.
"""
        interaction = self._retry(lambda: self.client.interactions.create(model=self.model, input=prompt))
        return (interaction.output_text or "").strip()

    def choose_anchors(self, marker_contexts: str) -> AnchorMap:
        prompt = f"""
For each evidence marker below, select an exact phrase from its nearby article text that should become the first-use hyperlink anchor.

Rules:
- phrase MUST be copied exactly from the supplied context, excluding the [[EV-...]] marker
- prefer a meaningful proper name, agency, company, document title, patent/contract identifier, program name, date phrase, or distinctive factual phrase
- prefer 1–8 words
- do not return Markdown markup around the phrase
- one answer per evidence_id

CONTEXTS:
{marker_contexts}
"""
        return self._structured(prompt, AnchorMap)

    def metadata(self, article: str, topic: str) -> ArticleMetadata:
        prompt = f"""
Create the publication package for this White Rabbit Report article.

TOPIC: {topic}

ARTICLE:
{article[:50000]}

Return:
- compelling title ideally ~60–70 characters
- meta title ~60 characters or less
- meta description ~150–160 characters
- SEO slug
- primary keyword
- useful secondary keywords
- 1–2 sentence sizzle/deck
- detailed 1980s airbrush movie-poster banner image prompt that visually expresses the investigation rather than merely illustrating the title
"""
        return self._structured(prompt, ArticleMetadata)
