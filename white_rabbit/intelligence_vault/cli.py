from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database import VaultDB
from .ingestion import ingest_document, import_structured


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "knowledge" / "intelligence_vault.db"


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
    serve = sub.add_parser("serve"); serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8765)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        from .web import serve
        serve(args.db, args.host, args.port); return 0
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
        elif args.command == "add-relationship": result = {"id": db.add_relationship(args.subject_id, args.object_id, args.relationship_type, directed=not args.undirected, classification=args.classification, historical_start={"value": args.start, "precision": "exact" if args.start and len(args.start) > 4 else "year"}, historical_end={"value": args.end, "precision": "exact" if args.end and len(args.end) > 4 else "year"})}
        elif args.command == "stats": result = db.stats()
        elif args.command == "review": result = db.list_review()
        elif args.command == "events": result = db.events_between(args.start, args.end)
        elif args.command == "export":
            args.path.parent.mkdir(parents=True, exist_ok=True); args.path.write_text(json.dumps(db.export(), ensure_ascii=False, indent=2), encoding="utf-8"); result = {"exported": str(args.path.resolve())}
        else: raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if result.get("error") else 0
