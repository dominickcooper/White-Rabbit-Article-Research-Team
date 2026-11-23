from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database import VaultDB
from .archive_importer import (
    ArchiveImportConfig, create_import_job, import_status, preview_archive,
    process_import_job, set_job_action,
)
from .ingestion import ingest_document, import_structured
from .backup import create_backup_bundle, restore_backup_bundle
from .extraction import (
    ExtractionConfig, bulk_decide, commit_approved, create_extraction_job, decide_proposal,
    extraction_review, extraction_status, prepare_manual_packet, process_extraction_job,
)
from .providers import build_provider


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "knowledge" / "intelligence_vault.db"


def _temporal_arg(value: str | None) -> dict:
    if not value:
        return {}
    precision = "year" if len(value) == 4 else "month" if len(value) == 7 else "exact"
    return {"value": value, "precision": precision, "certainty": "unknown"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m white_rabbit vault", description="White Rabbit Intelligence Vault")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    ingest = sub.add_parser("ingest"); ingest.add_argument("path", type=Path); ingest.add_argument("--classification", default="author_supplied"); ingest.add_argument("--authority-level", type=int, default=2)
    structured = sub.add_parser("import-json"); structured.add_argument("path", type=Path)
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--type", choices=["person", "organization", "event", "place"])
    show = sub.add_parser("show"); show.add_argument("entity_id")
    show_doc = sub.add_parser("show-document"); show_doc.add_argument("document_id")
    entity = sub.add_parser("add-entity"); entity.add_argument("entity_type", choices=["person", "organization", "event", "place"]); entity.add_argument("name"); entity.add_argument("--alias", action="append", default=[]); entity.add_argument("--description", default=""); entity.add_argument("--details-json", default="{}", help="Type-specific metadata as JSON")
    claim = sub.add_parser("add-claim"); claim.add_argument("statement"); claim.add_argument("--type", default="fact"); claim.add_argument("--status", default="DOCUMENTED RECORD"); claim.add_argument("--entity", action="append", default=[])
    rel = sub.add_parser("add-relationship"); rel.add_argument("subject_id"); rel.add_argument("object_id"); rel.add_argument("relationship_type"); rel.add_argument("--classification", default="DOCUMENTED RECORD"); rel.add_argument("--undirected", action="store_true"); rel.add_argument("--start"); rel.add_argument("--end")
    sub.add_parser("stats"); sub.add_parser("review")
    events = sub.add_parser("events"); events.add_argument("start"); events.add_argument("end")
    export = sub.add_parser("export"); export.add_argument("path", type=Path)
    backup = sub.add_parser("backup"); backup.add_argument("directory", type=Path)
    restore = sub.add_parser("restore"); restore.add_argument("directory", type=Path)
    extract = sub.add_parser("extract"); extract.add_argument("document", type=Path); extract.add_argument("--provider", choices=["gemini", "manual", "mock"], default="manual"); extract.add_argument("--model"); extract.add_argument("--allow-cloud", action="store_true"); extract.add_argument("--manual-results", type=Path); extract.add_argument("--chunk-size", type=int, default=12000); extract.add_argument("--overlap", type=int, default=1000); extract.add_argument("--max-chunks", type=int)
    prepare = sub.add_parser("extraction-prepare"); prepare.add_argument("document", type=Path); prepare.add_argument("output", type=Path); prepare.add_argument("--chunk-size", type=int, default=12000); prepare.add_argument("--overlap", type=int, default=1000); prepare.add_argument("--max-chunks", type=int)
    extract_status = sub.add_parser("extraction-status"); extract_status.add_argument("job_id")
    review = sub.add_parser("extraction-review"); review.add_argument("job_id"); review.add_argument("--approve", action="append", default=[]); review.add_argument("--reject", action="append", default=[]); review.add_argument("--match", action="append", default=[], metavar="PROPOSAL_ID=ENTITY_ID"); review.add_argument("--approve-all", action="store_true"); review.add_argument("--reject-all", action="store_true")
    commit = sub.add_parser("extraction-commit"); commit.add_argument("job_id")
    retry = sub.add_parser("extraction-retry"); retry.add_argument("job_id"); retry.add_argument("--provider", choices=["gemini", "manual", "mock"], required=True); retry.add_argument("--model"); retry.add_argument("--allow-cloud", action="store_true"); retry.add_argument("--manual-results", type=Path)
    archive_preview = sub.add_parser("archive-preview"); archive_preview.add_argument("source", type=Path)
    archive_import = sub.add_parser("archive-import"); archive_import.add_argument("source", type=Path); archive_import.add_argument("--investigation", default="Monarch Legacy Program"); archive_import.add_argument("--investigation-id"); archive_import.add_argument("--no-transcribe", action="store_true"); archive_import.add_argument("--ocr-images", action="store_true"); archive_import.add_argument("--no-thumbnails", action="store_true"); archive_import.add_argument("--whisper-model", default="small"); archive_import.add_argument("--whisper-device", default="cpu")
    archive_status = sub.add_parser("archive-status"); archive_status.add_argument("job_id"); archive_status.add_argument("--type"); archive_status.add_argument("--status"); archive_status.add_argument("--folder")
    archive_action = sub.add_parser("archive-action"); archive_action.add_argument("job_id"); archive_action.add_argument("action", choices=["pause", "resume", "cancel", "retry"])
    serve = sub.add_parser("serve"); serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8765)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        from .web import serve
        serve(args.db, args.host, args.port); return 0
    if args.command == "restore":
        result = {"restored": str(restore_backup_bundle(args.directory, args.db))}
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    if args.command == "extract":
        provider = build_provider(args.provider, model=args.model, allow_cloud=args.allow_cloud, manual_results=args.manual_results)
        with VaultDB(args.db) as db:
            job_id, created = create_extraction_job(
                db, args.document, provider,
                config=ExtractionConfig(args.chunk_size, args.overlap, args.max_chunks),
                allow_cloud=args.allow_cloud,
            )
            result = process_extraction_job(db, job_id, provider)
            result["created"] = created
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)); return 0
    if args.command == "extraction-prepare":
        output = prepare_manual_packet(
            args.document, args.output, config=ExtractionConfig(args.chunk_size, args.overlap, args.max_chunks)
        )
        print(json.dumps({"packet": str(output)}, indent=2)); return 0
    if args.command == "extraction-retry":
        provider = build_provider(args.provider, model=args.model, allow_cloud=args.allow_cloud, manual_results=args.manual_results)
        with VaultDB(args.db) as db:
            result = process_extraction_job(db, args.job_id, provider, retry_failed=True)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)); return 0
    if args.command == "archive-preview":
        print(json.dumps(preview_archive(args.source), ensure_ascii=False, indent=2, default=str)); return 0
    if args.command == "archive-import":
        config = ArchiveImportConfig(
            transcribe_media=not args.no_transcribe, ocr_images=args.ocr_images,
            create_thumbnails=not args.no_thumbnails, whisper_model=args.whisper_model,
            whisper_device=args.whisper_device,
        )
        with VaultDB(args.db) as db:
            job_id, _preview = create_import_job(
                db, args.source, investigation_name=args.investigation,
                investigation_id=args.investigation_id, config=config,
            )
            result = process_import_job(db, job_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)); return 0
    if args.command == "archive-action":
        with VaultDB(args.db) as db:
            result = set_job_action(db, args.job_id, args.action)
            if args.action in {"resume", "retry"}: result = process_import_job(db, args.job_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)); return 0
    with VaultDB(args.db) as db:
        if args.command == "init": result = {"database": str(args.db.resolve()), **db.stats()}
        elif args.command == "ingest":
            doc, rev, changed = ingest_document(db, args.path, source_classification=args.classification, authority_level=args.authority_level)
            result = {"document_id": doc, "revision_id": rev, "source_changed": changed}
        elif args.command == "import-json": result = import_structured(db, args.path)
        elif args.command == "search": result = db.search(args.query, args.type)
        elif args.command == "show": result = db.get_entity(args.entity_id) or {"error": "not found"}
        elif args.command == "show-document": result = db.get_document(args.document_id) or {"error": "not found"}
        elif args.command == "add-entity": result = {"id": db.add_entity(args.entity_type, args.name, aliases=args.alias, description=args.description, details=json.loads(args.details_json))}
        elif args.command == "add-claim": result = {"id": db.add_claim(args.statement, claim_type=args.type, status=args.status, entity_ids=args.entity)}
        elif args.command == "add-relationship": result = {"id": db.add_relationship(args.subject_id, args.object_id, args.relationship_type, directed=not args.undirected, classification=args.classification, historical_start=_temporal_arg(args.start), historical_end=_temporal_arg(args.end))}
        elif args.command == "stats": result = db.stats()
        elif args.command == "review": result = db.list_review()
        elif args.command == "events": result = db.events_between(args.start, args.end)
        elif args.command == "export":
            args.path.parent.mkdir(parents=True, exist_ok=True); args.path.write_text(json.dumps(db.export(), ensure_ascii=False, indent=2), encoding="utf-8"); result = {"exported": str(args.path.resolve())}
        elif args.command == "backup": result = {"backup": str(create_backup_bundle(db, args.directory))}
        elif args.command == "extraction-status": result = extraction_status(db, args.job_id)
        elif args.command == "archive-status": result = import_status(db, args.job_id, media_type=args.type, status=args.status, folder=args.folder)
        elif args.command == "extraction-review":
            for spec in args.match:
                if "=" not in spec: raise ValueError("--match requires PROPOSAL_ID=ENTITY_ID")
                proposal_id, entity_id = spec.split("=", 1)
                decide_proposal(db, args.job_id, proposal_id, "approve", known_entity_id=entity_id)
            for proposal_id in args.approve: decide_proposal(db, args.job_id, proposal_id, "approve")
            for proposal_id in args.reject: decide_proposal(db, args.job_id, proposal_id, "reject")
            if args.approve_all: bulk_decide(db, args.job_id, "approve")
            if args.reject_all: bulk_decide(db, args.job_id, "reject")
            result = extraction_review(db, args.job_id)
        elif args.command == "extraction-commit": result = {"committed": commit_approved(db, args.job_id)}
        else: raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if result.get("error") else 0
