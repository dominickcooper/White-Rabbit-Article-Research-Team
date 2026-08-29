from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .archive_retrieval import format_archive_memory, retrieve_archive_memory
from .archive_sync import SubstackArchiveSync
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

        print("[1/10] Retrieving relevant previous White Rabbit articles...")
        memories = retrieve_archive_memory(
            self.settings.archive_db_path,
            query=f"{topic} {angle}",
            chunk_limit=self.settings.archive_plan_chunks,
            article_limit=self.settings.archive_writer_articles,
        )
        publication_memory = format_archive_memory(memories)
        (research_dir / "previous_white_rabbit_memory.md").write_text(publication_memory, encoding="utf-8")
        print(f"      retrieved {len(memories)} prior articles as institutional memory")

        style = self.settings.style_path.read_text(encoding="utf-8")
        db = EvidenceDB(root / "evidence.sqlite3")
        try:
            print("[2/10] Building research plan...")
            plan_fn = self.provider.plan_research
            if _supports_kwarg(plan_fn, "publication_memory"):
                plan = plan_fn(topic, angle, style, self.settings.research_questions, publication_memory=publication_memory)
            else:
                plan = plan_fn(topic, angle, style, self.settings.research_questions)
            (research_dir / "research_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

            print("[3/10] Researching project/private sources...")
            docs = discover_local_documents(sources_folder)
            chunks = [c for d in docs for c in chunk_document(d)]
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

            print("[4/10] Running grounded web research...")
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
                            source_locator=url,
                            text=source_text,
                        )
                    except Exception as exc:
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

            print("[5/10] Building evidence-backed outline...")
            outline_fn = self.provider.build_outline
            if _supports_kwarg(outline_fn, "publication_memory"):
                outline = outline_fn(topic, angle, evidence_packet, style, publication_memory=publication_memory)
            else:
                outline = outline_fn(topic, angle, evidence_packet, style)
            (research_dir / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")

            print("[6/10] Writing article with evidence markers and verified internal-link candidates...")
            write_fn = self.provider.write_article
            if _supports_kwarg(write_fn, "publication_memory"):
                article = write_fn(topic, angle, outline, evidence_packet, style, publication_memory=publication_memory)
            else:
                article = write_fn(topic, angle, outline, evidence_packet, style)
            (drafts_dir / "article_with_evidence_markers.md").write_text(article, encoding="utf-8")

            print("[7/10] Auditing claims against evidence...")
            audit = self.provider.audit_article(article, evidence_packet)
            (research_dir / "source_audit.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")
            if not audit.pass_for_publish:
                print("      audit found blockers/warnings; running one evidence-constrained revision...")
                article = self.provider.revise_article(article, audit, evidence_packet, style)
                (drafts_dir / "article_with_evidence_markers.md").write_text(article, encoding="utf-8")
                audit = self.provider.audit_article(article, evidence_packet)
                (research_dir / "source_audit_after_revision.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")

            lookup = db.evidence_lookup()
            unknown_markers = sorted(set(re.findall(r"\[\[(EV-\d{4,})\]\]", article)) - set(lookup))
            if unknown_markers:
                raise RuntimeError(f"Article contains invented/unknown evidence markers: {unknown_markers}")

            print("[8/10] Building exact phrase → source CSV and inserting external links...")
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

            print("[9/10] Exporting DOCX/HTML/package...")
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

            print("[10/10] Finalizing run summary...")
            summary = {
                "project": project,
                "project_sources": str(sources_folder.resolve()),
                "previous_articles_used_for_memory": [m.article.canonical_url for m in memories],
                "evidence_items": len(db.list_evidence()),
                "public_links_inserted": len(successful),
                "unmatched_anchors": len(missing),
                "source_audit_pass": audit.pass_for_publish,
            }
            (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

            print(f"\nCOMPLETE: {output_dir}")
            print(f"DOCX: {docx_path}")
            print(f"Project source folder: {sources_folder}")
            print(f"Previous White Rabbit articles consulted: {len(memories)}")
            print(f"Evidence items: {len(db.list_evidence())}")
            print(f"Public links inserted: {len(successful)}")
            print(f"Unmatched anchors: {len(missing)}")
            print(f"Final source audit pass: {audit.pass_for_publish}")
            return output_dir
        finally:
            db.close()
