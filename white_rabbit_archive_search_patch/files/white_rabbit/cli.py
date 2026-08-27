from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archive_db import ArchiveDB
from .archive_sync import SubstackArchiveSync
from .archive_retrieval import retrieve_archive_memory
from .config import load_settings
from .gemini_provider import GeminiProvider
from .pipeline import SingleArticlePipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="white_rabbit", description="White Rabbit Report research/writing pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Verify configuration and Gemini connectivity")

    run = sub.add_parser("run", help="Research and produce one evidence-backed article")
    run.add_argument("topic")
    run.add_argument("--project", default=None, help="Project ID / workspace folder name")
    run.add_argument("--angle", default="", help="Optional thesis/angle to test, not assume")
    run.add_argument("--sources", type=Path, default=None, help="Optional override for project-local source folder")
    run.add_argument("--no-archive-sync", action="store_true", help="Skip the automatic White Rabbit archive sync for this run")

    archive = sub.add_parser("archive", help="Manage the Previous White Rabbit Articles corpus")
    archive_sub = archive.add_subparsers(dest="archive_command", required=True)
    sync_cmd = archive_sub.add_parser("sync", help="Discover/download White Rabbit Substack articles not already stored")
    sync_cmd.add_argument("--refresh", action="store_true", help="Re-fetch existing posts too, to detect edits")
    archive_sub.add_parser("status", help="Show the local White Rabbit article archive status")
    search_cmd = archive_sub.add_parser("search", help="Search prior White Rabbit articles for institutional memory")
    search_cmd.add_argument("query", help="Topic, entity, phrase, or research question")
    search_cmd.add_argument("--limit", type=int, default=8, help="Maximum prior articles to return (default: 8)")
    search_cmd.add_argument("--links", type=int, default=8, help="Maximum prior links to display per article (default: 8)")
    search_cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return p


def _archive_sync(settings, *, refresh_existing: bool = False) -> dict:
    if not settings.substack_url:
        raise RuntimeError("WR_SUBSTACK_URL is not configured in .env")
    syncer = SubstackArchiveSync(
        publication_url=settings.substack_url,
        archive_root=settings.archive_root,
        db_path=settings.archive_db_path,
        timeout=settings.http_timeout,
        sitemap_url=settings.sitemap_url,
        request_delay_ms=settings.archive_request_delay_ms,
    )
    try:
        return syncer.sync(refresh_existing=refresh_existing)
    finally:
        syncer.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()

    if args.command == "archive":
        if args.archive_command == "sync":
            try:
                report = _archive_sync(settings, refresh_existing=args.refresh)
            except Exception as exc:
                print(f"ERROR: {exc}")
                return 2
            print(json.dumps({
                "discovered": report["discovered"],
                "new": len(report["new"]),
                "updated": len(report["updated"]),
                "unchanged_after_refresh": len(report["unchanged"]),
                "skipped_existing": len(report["skipped_existing"]),
                "preview_only": len(report["preview_only"]),
                "errors": len(report["errors"]),
            }, indent=2))
            if report["preview_only"]:
                print("WARNING: Some paid/subscriber posts appear to contain preview text only. They are flagged, not silently treated as full articles.")
            return 0
        if args.archive_command == "status":
            db = ArchiveDB(settings.archive_db_path)
            try:
                status = db.status()
            finally:
                db.close()
            print(json.dumps(status, indent=2))
            print(f"Archive folder: {settings.archive_root}")
            return 0
        if args.archive_command == "search":
            limit = max(1, min(int(args.limit), 25))
            link_limit = max(0, min(int(args.links), 30))
            memories = retrieve_archive_memory(
                settings.archive_db_path,
                query=args.query,
                chunk_limit=max(10, limit * 2),
                article_limit=limit,
            )
            if args.json:
                payload = []
                for memory in memories:
                    a = memory.article
                    payload.append({
                        "wr_id": a.wr_id,
                        "title": a.title,
                        "url": a.canonical_url,
                        "published_date": a.published_date,
                        "content_status": a.content_status,
                        "relevance": round(memory.score, 4),
                        "matched_terms": list(memory.matched_terms),
                        "excerpt": memory.excerpt,
                        "links": memory.links[:link_limit],
                    })
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0

            if not memories:
                print("No relevant Previous White Rabbit Articles found.")
                return 0

            print(f"PREVIOUS WHITE RABBIT ARCHIVE SEARCH: {args.query}")
            print("=" * 78)
            for index, memory in enumerate(memories, start=1):
                a = memory.article
                print()
                print(f"{index}. {a.title}")
                print(f"   {a.wr_id} | relevance {memory.score:.0%} | {a.content_status}")
                if memory.matched_terms:
                    print(f"   Matched: {', '.join(memory.matched_terms)}")
                print(f"   {a.canonical_url}")
                if memory.excerpt:
                    excerpt = memory.excerpt.replace("\n", " ").strip()
                    print(f"   Excerpt: {excerpt}")
                links = memory.links[:link_limit]
                if links:
                    print("   Prior links to reopen/verify:")
                    for link in links:
                        anchor = str(link.get("anchor", "")).strip() or "(no anchor)"
                        print(f"     - {anchor}: {link.get('url', '')}")
            print()
            print("NOTE: Prior White Rabbit articles are research leads/internal-link candidates, not proof. Re-verify original sources before using factual claims.")
            return 0

    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY is missing. Copy .env.example to .env and add the key.")
        return 2
    provider = GeminiProvider(settings.gemini_api_key, settings.model)
    if args.command == "doctor":
        print(f"Model: {settings.model}")
        print(f"Substack: {settings.substack_url or '(not configured)'}")
        print(provider.doctor())
        return 0

    pipeline = SingleArticlePipeline(settings, provider)
    pipeline.run(
        topic=args.topic,
        project=args.project,
        angle=args.angle,
        sources_folder=args.sources,
        skip_archive_sync=args.no_archive_sync,
    )
    return 0
