from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .archive_retrieval import format_archive_memory, retrieve_archive_memory
from .archive_reranker import (
    apply_archive_rerank,
    format_candidates_for_rerank,
    format_curated_archive_memory,
    rerank_audit_payload,
)
from .archive_sync import SubstackArchiveSync
from .archive_voice import format_voice_reference_packet, retrieve_voice_references
from .config import Settings
from .evidence_db import EvidenceDB
from .local_sources import chunk_document, discover_local_documents, rank_chunks
from .source_mapper import build_source_rows, format_contexts, marker_contexts, write_source_csv
from .web_fetch import fetch_page, is_blocked_source, is_grounding_redirect, resolve_public_url
from .publishing.substack_source_linker import (
    Source,
    create_report,
    insert_links,
    markdown_to_docx,
    markdown_to_html,
    wrap_html,
)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return s[:80] or "article"


def normalize_public_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
    except Exception:
        return url.strip()


def verify_excerpt(excerpt: str | None, source_text: str) -> bool:
    if not excerpt:
        return False
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    e = norm(excerpt)
    t = norm(source_text)
    return bool(e) and e in t


def _supports_kwarg(fn, name: str) -> bool:
    try:
        return name in inspect.signature(fn).parameters
    except Exception:
        return False


def _call_supported(fn, *args, **kwargs):
    """Call a provider with new workflow context while preserving older providers."""
    accepted = {key: value for key, value in kwargs.items() if _supports_kwarg(fn, key)}
    return fn(*args, **accepted)


def _source_corpus_packet(documents, *, per_document: int = 18000, total: int = 140000) -> str:
    """Create a bounded pre-research corpus packet while inventorying every local item."""
    inventory = [f"- {doc.path.name}: {len(doc.text)} extracted characters" for doc in documents]
    sections = ["# SOURCE INVENTORY", *inventory, "", "# SOURCE EXCERPTS"]
    remaining = total
    for doc in documents:
        if remaining <= 0:
            sections.append(f"\n## {doc.path.name}\n[Inventory retained; excerpt omitted by context bound.]")
            continue
        excerpt = doc.text[: min(per_document, remaining)].strip()
        remaining -= len(excerpt)
        status = "complete extracted text" if len(excerpt) == len(doc.text) else "bounded excerpt; full source remains available downstream"
        sections.append(f"\n## {doc.path.name}\nReading status: {status}\n\n{excerpt}")
    return "\n".join(sections)


def _source_thesis_markdown(thesis) -> str:
    data = thesis.model_dump()
    def bullets(values):
        return "\n".join(f"- {value}" for value in values) or "- None recorded."
    return f"""# Source thesis

Thesis version: {data['thesis_version']}
Thesis status: {data['status']}

## Author's explicit assignment

{data['author_objective']}

## Source inventory and reading status

{bullets(data['source_inventory'])}

## Principal source-derived thesis

{data['principal_thesis']}

## Supporting source-derived subtheories

{bullets(data['supporting_theories'])}

## Key testimony and witness accounts

{bullets(data['accepted_testimony'])}

## Published White Rabbit canon relevant to the thesis

{bullets(data['canon_premises'])}

## Significant entities, operations, companies, agencies, and events

{bullets(data['key_entities'])}

## Initial connection chains

{bullets(data['initial_connections'])}

## Strongest unresolved questions

{bullets(data['unresolved_questions'])}

## Predicted documentary footprints

{bullets(data['predicted_footprints'])}

## Genuine contradictions already inside the supplied corpus

{bullets(data['source_conflicts'])}

## Specific external research objectives

{bullets(data['external_research_objectives'])}
"""


def _writer_packet_markdown(packet) -> str:
    data = packet.model_dump()
    def section(title, values):
        body = "\n".join(f"- {value}" for value in values) or "- None recorded."
        return f"## {title}\n\n{body}"
    sections = [
        "# Writer packet",
        f"## Original author objective\n\n{data['author_objective']}",
        f"## Locked source-derived thesis and version\n\nVersion {data['thesis_version']}: {data['locked_thesis']}",
        section("Strongest surviving supported findings", data["strongest_findings"]),
        section("Accepted testimony and provenance", data["accepted_testimony"]),
        section("Published White Rabbit canon used as premises", data["canon_premises"]),
        section("Important characters and relationships", data["characters_and_relationships"]),
        section("Consequential connection chains", data["connection_chains"]),
        section("Investigated rabbit holes", data["investigated_rabbit_holes"]),
        section("Crucial quotations, document identifiers, dates, and locators", data["documentary_details"]),
        section("Timeline", data["chronology"]),
        section("Significant new details and narrative surprises", data["narrative_surprises"]),
        section("Material contradictions", data["contradictions"]),
        section("Critical factual boundaries that must survive drafting", data["factual_boundaries"]),
        section("Reader-facing source and link locators", data["source_locators"]),
        section("Recommended reveal sequence", data["reveal_sequence"]),
        section("Relevant Gold voice passages and behavioral lessons", data["gold_voice_lessons"]),
        "## Writer context boundary\n\nDraft from this packet, Source Thesis, Story Spine/outline, selected receipts and voice references—not the complete adversarial research bureaucracy.",
        "## Auditor context boundary\n\nThe independent auditor receives the complete evidence record and returns targeted minimum corrections.",
    ]
    return "\n\n".join(sections) + "\n"


class SingleArticlePipeline:
    def __init__(self, settings: Settings, provider):
        self.settings = settings
        self.provider = provider

    def _sync_archive(self) -> dict | None:
        if not self.settings.substack_url:
            print("[0/10] White Rabbit archive sync skipped: WR_SUBSTACK_URL is not configured.")
            return None
        print("[0/10] Synchronizing Previous White Rabbit Articles...")
        syncer = SubstackArchiveSync(
            publication_url=self.settings.substack_url,
            archive_root=self.settings.archive_root,
            db_path=self.settings.archive_db_path,
            timeout=self.settings.http_timeout,
            sitemap_url=self.settings.sitemap_url,
            request_delay_ms=self.settings.archive_request_delay_ms,
        )
        try:
            report = syncer.sync(refresh_existing=False)
        finally:
            syncer.close()
        print(
            f"      archive current: {report['discovered']} discovered; "
            f"{len(report['new'])} new; {len(report['skipped_existing'])} already local; "
            f"{len(report['preview_only'])} preview-only"
        )
        return report

    def run(
        self,
        *,
        topic: str,
        project: str | None = None,
        angle: str = "",
        sources_folder: Path | None = None,
        skip_archive_sync: bool = False,
    ) -> Path:
        project = project or slugify(topic)
        root = self.settings.workspace / project
        research_dir = root / "research"
        drafts_dir = root / "drafts"
        output_dir = root / "output"
        for d in (research_dir, drafts_dir, output_dir):
            d.mkdir(parents=True, exist_ok=True)

        default_sources = self.settings.project_sources_root / project / "sources"
        default_sources.mkdir(parents=True, exist_ok=True)
        sources_folder = Path(sources_folder) if sources_folder else default_sources

        if self.settings.archive_sync_before_run and not skip_archive_sync:
            self._sync_archive()
        else:
            print("[0/10] Automatic White Rabbit archive sync disabled/skipped for this run.")

        print("[1/10] Retrieving and judging previous White Rabbit articles...")
        candidate_limit = max(self.settings.archive_writer_articles, self.settings.archive_rerank_candidates)
        candidates = retrieve_archive_memory(
            self.settings.archive_db_path,
            query=f"{topic} {angle}",
            chunk_limit=max(self.settings.archive_plan_chunks, candidate_limit * 2),
            article_limit=candidate_limit,
        )
        candidate_memory = format_archive_memory(candidates)
        (research_dir / "previous_white_rabbit_candidates.md").write_text(candidate_memory, encoding="utf-8")

        rerank_rows: list[dict] = []
        if (
            self.settings.archive_rerank_enabled
            and candidates
            and hasattr(self.provider, "rerank_archive_memory")
        ):
            print(f"      sending top {len(candidates)} archive candidates to Gemini relevance judge...")
            try:
                candidate_packet = format_candidates_for_rerank(candidates)
                batch = self.provider.rerank_archive_memory(topic, angle, candidate_packet)
                reranked = apply_archive_rerank(
                    candidates,
                    batch,
                    min_score=self.settings.archive_rerank_min_score,
                    direct_matches_always_include=True,
                )
                rerank_rows = rerank_audit_payload(reranked)
                selected = [r for r in reranked if r.included][: self.settings.archive_writer_articles]
                memories = [r.memory for r in selected]
                publication_memory = format_curated_archive_memory(selected)
                print(
                    f"      Gemini retained {len(memories)}/{len(candidates)} prior articles "
                    f"(threshold {self.settings.archive_rerank_min_score}/5; direct matches auto-retained)"
                )
            except Exception as exc:
                print(f"      WARNING: Gemini archive reranker failed: {exc}")
                direct = [m for m in candidates if m.connection_tier == "DIRECT" or m.exact_phrases]
                memories = direct[: self.settings.archive_writer_articles]
                publication_memory = format_archive_memory(memories)
                print(f"      fallback retained {len(memories)} deterministic direct matches only")
        else:
            memories = candidates[: self.settings.archive_writer_articles]
            publication_memory = format_archive_memory(memories)
            print(f"      Gemini reranker disabled/unavailable; using top {len(memories)} local archive matches")

        voice_result = retrieve_voice_references(
            self.settings.archive_db_path,
            f"{topic} {angle}",
            root=self.settings.root,
            passage_limit=8,
        )
        voice_memory = format_voice_reference_packet(voice_result)
        canon_memory = publication_memory
        publication_memory = canon_memory + "\n\n" + voice_memory

        (research_dir / "previous_white_rabbit_rerank.json").write_text(
            json.dumps(rerank_rows, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (research_dir / "previous_white_rabbit_canon.md").write_text(canon_memory, encoding="utf-8")
        (research_dir / "previous_white_rabbit_voice.md").write_text(voice_memory, encoding="utf-8")
        (research_dir / "previous_white_rabbit_memory.md").write_text(publication_memory, encoding="utf-8")

        style = self.settings.style_path.read_text(encoding="utf-8")
        db = EvidenceDB(root / "evidence.sqlite3")
        try:
            print("[2/12] Reading author-selected sources and locking Source Thesis...")
            docs = discover_local_documents(sources_folder)
            chunks = [c for d in docs for c in chunk_document(d)]
            corpus_packet = _source_corpus_packet(docs)
            (research_dir / "source_inventory.json").write_text(
                json.dumps([
                    {"path": str(doc.path), "title": doc.title, "extracted_characters": len(doc.text)}
                    for doc in docs
                ], indent=2, ensure_ascii=False), encoding="utf-8"
            )
            derive_fn = getattr(self.provider, "derive_source_thesis", None)
            if derive_fn is not None:
                source_thesis_model = _call_supported(
                    derive_fn, topic, angle, corpus_packet, canon_memory=canon_memory
                )
                source_thesis = _source_thesis_markdown(source_thesis_model)
            else:
                source_thesis_model = None
                source_thesis = f"""# Source thesis

Thesis version: 1
Thesis status: AUTHOR THESIS DECISION REQUIRED

## Author's explicit assignment

{topic}{(': ' + angle) if angle else ''}

## Source inventory and reading status

{chr(10).join('- ' + doc.path.name for doc in docs) or '- No supported local sources discovered.'}

## Principal source-derived thesis

Provider does not implement source-thesis derivation. Complete this artifact before treating the legacy plan as editorially approved.
"""
            (research_dir / "SOURCE_THESIS.md").write_text(source_thesis, encoding="utf-8")

            print("[3/12] Building thesis-fidelity research plan...")
            plan_fn = self.provider.plan_research
            plan = _call_supported(
                plan_fn, topic, angle, style, self.settings.research_questions,
                publication_memory=publication_memory,
                canon_memory=canon_memory,
                source_thesis=source_thesis,
            )
            (research_dir / "research_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

            print("[4/12] Researching project/private sources...")
            qtext = topic + " " + " ".join(q.question + " " + q.search_query for q in plan.questions)
            for chunk in rank_chunks(chunks, qtext, self.settings.local_chunks):
                source_id = db.add_source(
                    title=chunk.document.title,
                    source_kind="private_file",
                    file_path=str(chunk.document.path),
                    reliability="unknown",
                )
                question = plan.questions[0].question if plan.questions else topic
                extraction = self.provider.extract_evidence_from_text(
                    topic=topic,
                    research_question=question,
                    source_title=chunk.document.title,
                    source_locator=f"{chunk.document.path} [chunk {chunk.index}]",
                    text=chunk.text,
                )
                for item in extraction.items:
                    db.add_evidence(source_id, item, excerpt_verified=verify_excerpt(item.excerpt, chunk.text))

            print("[5/12] Running grounded web research...")
            web_log: list[dict] = []
            processed_urls: set[str] = set()
            for i, q in enumerate(plan.questions, start=1):
                print(f"      query {i}/{len(plan.questions)}: {q.search_query}")
                result = self.provider.web_research(q.id, q.question, q.search_query)
                db.add_research_run(q.id, q.search_query, result.notes, [c.model_dump() for c in result.citations])
                web_log.append(result.model_dump())
                for citation in result.citations[: self.settings.web_sources_per_query]:
                    raw_url = normalize_public_url(citation.url)
                    if not raw_url:
                        continue
                    url = raw_url
                    if is_grounding_redirect(raw_url):
                        print(f"        resolving Google grounding redirect...")
                        url = normalize_public_url(resolve_public_url(raw_url, timeout=self.settings.http_timeout))
                    if not url or url in processed_urls:
                        continue
                    processed_urls.add(url)
                    if is_blocked_source(url):
                        print(f"        skip paywalled/blocked host: {url}")
                        continue
                    if is_grounding_redirect(url):
                        print(f"        skip unresolved grounding wrapper: {url[:80]}...")
                        continue
                    title = citation.title or url
                    print(f"        source: {url}")
                    source_id = db.add_source(title=title, source_kind="public_web", url=url)
                    source_text = ""
                    try:
                        page = fetch_page(url, timeout=self.settings.http_timeout)
                        source_text = page.text
                        if len(source_text.strip()) < 400:
                            raise ValueError("retrieved page had too little extractable text")
                        print(f"        extracting from page text ({len(source_text)} chars)...")
                        extraction = self.provider.extract_evidence_from_text(
                            topic=topic,
                            research_question=q.question,
                            source_title=page.title or title,
                            source_locator=page.url or url,
                            text=source_text,
                        )
                    except Exception as exc:
                        if is_grounding_redirect(url):
                            print(
                                f"        WARNING: grounding citation could not be resolved to a direct public URL; "
                                f"skipping URL Context: {url} ({exc})"
                            )
                            continue
                        print(f"        fetch fallback via Gemini URL Context: {url} ({exc})")
                        try:
                            extraction = self.provider.extract_evidence_from_url(
                                topic=topic,
                                research_question=q.question,
                                source_title=title,
                                url=url,
                            )
                            print("        URL Context returned structured evidence")
                        except Exception as url_exc:
                            print(f"        WARNING: source could not be analyzed: {url_exc}")
                            continue
                    print(f"        kept {len(extraction.items)} evidence items")
                    for item in extraction.items:
                        verified = verify_excerpt(item.excerpt, source_text) if source_text else False
                        db.add_evidence(source_id, item, excerpt_verified=verified)
            (research_dir / "web_research.json").write_text(json.dumps(web_log, indent=2, ensure_ascii=False), encoding="utf-8")

            evidence_packet = db.build_packet(limit=self.settings.max_evidence_items)
            (research_dir / "evidence_packet.md").write_text(evidence_packet, encoding="utf-8")
            if not evidence_packet.strip():
                raise RuntimeError("No evidence was extracted. Aborting before article generation.")

            print("[6/12] Building evidence-backed showrunner outline...")
            outline_fn = self.provider.build_outline
            outline = _call_supported(
                outline_fn, topic, angle, evidence_packet, style,
                publication_memory=publication_memory,
                canon_memory=canon_memory,
                source_thesis=source_thesis,
            )
            (research_dir / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")

            print("[7/12] Building controlled Writer Packet...")
            packet_fn = getattr(self.provider, "build_writer_packet", None)
            if packet_fn is not None:
                packet_model = _call_supported(
                    packet_fn,
                    source_thesis=source_thesis,
                    outline=outline,
                    evidence_packet=evidence_packet,
                    canon_memory=canon_memory,
                    voice_memory=voice_memory,
                )
                writer_packet = _writer_packet_markdown(packet_model)
            else:
                writer_packet = (
                    "# Writer packet\n\n## Locked source-derived thesis and version\n\n" +
                    source_thesis + "\n\n## Recommended reveal sequence\n\n" +
                    outline.model_dump_json(indent=2) +
                    "\n\n## Auditor context boundary\n\nThe auditor retains the complete evidence packet.\n"
                )
            (research_dir / "WRITER_PACKET.md").write_text(writer_packet, encoding="utf-8")

            print("[8/12] Writing from the controlled handoff...")
            write_fn = self.provider.write_article
            article = _call_supported(
                write_fn, topic, angle, outline, evidence_packet, style,
                publication_memory=publication_memory,
                canon_memory=canon_memory,
                voice_memory=voice_memory,
                source_thesis=source_thesis,
                writer_packet=writer_packet,
            )
            (drafts_dir / "article_with_evidence_markers.md").write_text(article, encoding="utf-8")

            print("[9/12] Independently auditing claims against the complete record...")
            audit_fn = self.provider.audit_article
            audit = _call_supported(
                audit_fn, article, evidence_packet,
                publication_memory=publication_memory,
                canon_memory=canon_memory,
                source_thesis=source_thesis,
            )
            (research_dir / "source_audit.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")
            if not audit.pass_for_publish:
                print("      audit found blockers/warnings; running one surgical evidence-constrained revision...")
                revise_fn = self.provider.revise_article
                article = _call_supported(
                    revise_fn, article, audit, evidence_packet, style,
                    publication_memory=publication_memory,
                    canon_memory=canon_memory,
                    voice_memory=voice_memory,
                    source_thesis=source_thesis,
                )
                (drafts_dir / "article_with_evidence_markers.md").write_text(article, encoding="utf-8")
                audit = _call_supported(
                    audit_fn, article, evidence_packet,
                    publication_memory=publication_memory,
                    canon_memory=canon_memory,
                    source_thesis=source_thesis,
                )
                (research_dir / "source_audit_after_revision.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")

            lookup = db.evidence_lookup()
            unknown_markers = sorted(set(re.findall(r"\[\[(EV-\d{4,})\]\]", article)) - set(lookup))
            if unknown_markers:
                raise RuntimeError(f"Article contains invented/unknown evidence markers: {unknown_markers}")

            print("[10/12] Building exact phrase → source CSV and inserting external links...")
            contexts = marker_contexts(article)
            anchor_map = self.provider.choose_anchors(format_contexts(contexts))
            unlinked, source_rows, anchor_warnings = build_source_rows(article, anchor_map, lookup)
            (drafts_dir / "article_unlinked.md").write_text(unlinked, encoding="utf-8")
            csv_path = output_dir / "sources.csv"
            write_source_csv(csv_path, source_rows)
            (research_dir / "anchor_warnings.json").write_text(json.dumps(anchor_warnings, indent=2), encoding="utf-8")

            linker_sources = [Source(r.source_number, r.phrase, r.link) for r in source_rows]
            linked, successful, missing = insert_links(unlinked, linker_sources)
            linked_md_path = output_dir / "article_linked.md"
            linked_md_path.write_text(linked, encoding="utf-8")

            print("[11/12] Exporting DOCX/HTML/package...")
            docx_path = output_dir / "article_substack.docx"
            html_path = output_dir / "article_substack.html"
            report_path = output_dir / "article_link_report.txt"
            markdown_to_docx(linked, docx_path)
            html_body = markdown_to_html(linked)
            html_path.write_text(wrap_html(html_body, outline.working_title), encoding="utf-8")
            report = create_report(project, drafts_dir / "article_unlinked.md", csv_path, successful, missing)
            report_path.write_text(report, encoding="utf-8")
            metadata = self.provider.metadata(unlinked, topic)
            (output_dir / "metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

            print("[12/12] Recording independent quality-gate state...")
            quality_gates = {
                "A": {"status": "PASS", "evidence": "Legacy export and source-link package completed."},
                "B": {"status": "PASS" if source_thesis_model is not None else "NEEDS REVIEW",
                      "evidence": "Source inventory and Source Thesis recorded before planning."},
                "C": {"status": "NEEDS REVIEW", "evidence": "Legacy provider produced a locked thesis; independent thesis-fidelity review is still required."},
                "D": {"status": "NOT RUN", "evidence": "Independent narrative review is not automated by the legacy provider."},
                "E": {"status": "NOT RUN", "evidence": "Independent Gold/semantic voice review is not automated by the legacy provider."},
                "F": {"status": "PASS" if audit.pass_for_publish else "FAIL", "evidence": "Independent provider evidence audit result."},
                "G": {"status": "AUTHOR APPROVAL REQUIRED", "evidence": "Software cannot approve publication."},
                "publication_status": "AUTHOR APPROVAL REQUIRED",
            }
            (output_dir / "quality_gates.json").write_text(
                json.dumps(quality_gates, indent=2), encoding="utf-8"
            )

            print("      finalizing run summary...")
            summary = {
                "project": project,
                "project_sources": str(sources_folder.resolve()),
                "previous_articles_used_for_memory": [m.article.canonical_url for m in memories],
                "archive_reranker_enabled": self.settings.archive_rerank_enabled,
                "archive_rerank_candidates": len(candidates),
                "archive_rerank_results": rerank_rows,
                "evidence_items": len(db.list_evidence()),
                "public_links_inserted": len(successful),
                "unmatched_anchors": len(missing),
                "source_audit_pass": audit.pass_for_publish,
                "evidence_audit_pass": audit.pass_for_publish,
                "publication_status": "AUTHOR APPROVAL REQUIRED",
                "quality_gates": quality_gates,
            }
            (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

            print(f"\nCOMPLETE: {output_dir}")
            print(f"DOCX: {docx_path}")
            print(f"Project source folder: {sources_folder}")
            print(f"Previous White Rabbit articles consulted: {len(memories)}")
            print(f"Evidence items: {len(db.list_evidence())}")
            print(f"Public links inserted: {len(successful)}")
            print(f"Unmatched anchors: {len(missing)}")
            print(f"Final evidence audit pass: {audit.pass_for_publish}")
            print("Publication status: AUTHOR APPROVAL REQUIRED")
            return output_dir
        finally:
            db.close()
