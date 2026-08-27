from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .config import Settings
from .evidence_db import EvidenceDB
from .local_sources import chunk_document, discover_local_documents, rank_chunks
from .schemas import CitationRef
from .source_mapper import build_source_rows, format_contexts, marker_contexts, write_source_csv
from .web_fetch import fetch_page
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


class SingleArticlePipeline:
    def __init__(self, settings: Settings, provider):
        self.settings = settings
        self.provider = provider

    def run(self, *, topic: str, project: str | None = None, angle: str = "", sources_folder: Path | None = None) -> Path:
        project = project or slugify(topic)
        root = self.settings.workspace / project
        research_dir = root / "research"
        drafts_dir = root / "drafts"
        output_dir = root / "output"
        for d in (research_dir, drafts_dir, output_dir):
            d.mkdir(parents=True, exist_ok=True)

        style = self.settings.style_path.read_text(encoding="utf-8")
        db = EvidenceDB(root / "evidence.sqlite3")
        try:
            print("[1/8] Building research plan...")
            plan = self.provider.plan_research(topic, angle, style, self.settings.research_questions)
            (research_dir / "research_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

            print("[2/8] Researching private/local sources...")
            if sources_folder:
                docs = discover_local_documents(Path(sources_folder))
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

            print("[3/8] Running grounded web research...")
            web_log: list[dict] = []
            processed_urls: set[str] = set()
            for i, q in enumerate(plan.questions, start=1):
                print(f"      query {i}/{len(plan.questions)}: {q.search_query}")
                result = self.provider.web_research(q.id, q.question, q.search_query)
                db.add_research_run(q.id, q.search_query, result.notes, [c.model_dump() for c in result.citations])
                web_log.append(result.model_dump())
                for citation in result.citations[: self.settings.web_sources_per_query]:
                    url = normalize_public_url(citation.url)
                    if not url or url in processed_urls:
                        continue
                    processed_urls.add(url)
                    title = citation.title or url
                    source_id = db.add_source(title=title, source_kind="public_web", url=url)
                    source_text = ""
                    try:
                        page = fetch_page(url, timeout=self.settings.http_timeout)
                        source_text = page.text
                        if len(source_text.strip()) < 400:
                            raise ValueError("retrieved page had too little extractable text")
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
                        except Exception as url_exc:
                            print(f"        WARNING: source could not be analyzed: {url_exc}")
                            continue
                    for item in extraction.items:
                        verified = verify_excerpt(item.excerpt, source_text) if source_text else False
                        db.add_evidence(source_id, item, excerpt_verified=verified)
            (research_dir / "web_research.json").write_text(json.dumps(web_log, indent=2, ensure_ascii=False), encoding="utf-8")

            evidence_packet = db.build_packet(limit=self.settings.max_evidence_items)
            (research_dir / "evidence_packet.md").write_text(evidence_packet, encoding="utf-8")
            if not evidence_packet.strip():
                raise RuntimeError("No evidence was extracted. Aborting before article generation.")

            print("[4/8] Building evidence-backed outline...")
            outline = self.provider.build_outline(topic, angle, evidence_packet, style)
            (research_dir / "outline.json").write_text(outline.model_dump_json(indent=2), encoding="utf-8")

            print("[5/8] Writing article with evidence markers...")
            article = self.provider.write_article(topic, angle, outline, evidence_packet, style)
            (drafts_dir / "article_with_evidence_markers.md").write_text(article, encoding="utf-8")

            print("[6/8] Auditing claims against evidence...")
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

            print("[7/8] Building exact phrase → source CSV and inserting links...")
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

            print("[8/8] Exporting DOCX/HTML/package...")
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

            print(f"\nCOMPLETE: {output_dir}")
            print(f"DOCX: {docx_path}")
            print(f"Evidence items: {len(db.list_evidence())}")
            print(f"Public links inserted: {len(successful)}")
            print(f"Unmatched anchors: {len(missing)}")
            print(f"Final source audit pass: {audit.pass_for_publish}")
            return output_dir
        finally:
            db.close()
