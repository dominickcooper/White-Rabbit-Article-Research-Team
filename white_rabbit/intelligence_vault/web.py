from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import sqlite3
from threading import Thread
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field

from .database import VaultDB
from .archive_importer import (
    ArchiveImportConfig, create_import_job, import_status, preview_archive,
    process_import_job, report_path, set_job_action,
)
from .schema import TemporalValue
from .extraction import (
    ExtractionConfig, commit_approved, create_extraction_job,
    create_extraction_job_from_revision, decide_proposal,
    extraction_review, extraction_status, process_extraction_job,
)
from .providers import build_provider
from .exploration import (
    connection_paths, entity_profile, graph_data, investigations_data,
    relationship_detail, timeline_csv, timeline_data,
)


MAX_BODY_BYTES = 256 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
STATIC_ROOT = Path(__file__).with_name("static")


class APIEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["person", "organization", "event", "place"]
    name: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=10000)
    details: dict = Field(default_factory=dict)


class APIClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=10000)
    original_wording: str | None = Field(default=None, max_length=10000)
    claim_type: str = Field(default="fact", max_length=100)
    status: str = Field(default="DOCUMENTED RECORD", max_length=100)
    entity_ids: list[str] = Field(default_factory=list, max_length=500)
    historical_start: TemporalValue = Field(default_factory=TemporalValue)
    historical_end: TemporalValue = Field(default_factory=TemporalValue)


class APIRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: str = Field(min_length=1, max_length=100)
    object_id: str = Field(min_length=1, max_length=100)
    relationship_type: str = Field(min_length=1, max_length=200)
    directed: bool = True
    classification: str = Field(default="DOCUMENTED RECORD", max_length=100)
    historical_start: TemporalValue = Field(default_factory=TemporalValue)
    historical_end: TemporalValue = Field(default_factory=TemporalValue)


class APIExtractionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: str = Field(min_length=1, max_length=2000)
    provider: Literal["gemini", "manual", "mock"]
    model: str | None = Field(default=None, max_length=200)
    allow_cloud: bool = False
    manual_results: str | None = Field(default=None, max_length=2000)
    chunk_size: int = Field(default=12000, ge=500, le=100000)
    overlap: int = Field(default=1000, ge=0, le=20000)
    max_chunks: int | None = Field(default=None, ge=1, le=10000)


class APIProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "reject"]
    known_entity_id: str | None = Field(default=None, max_length=100)


class APIExtractionRetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["gemini", "manual", "mock"]
    model: str | None = Field(default=None, max_length=200)
    allow_cloud: bool = False
    manual_results: str | None = Field(default=None, max_length=2000)


class APIArchivePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=2000)


class APIArchiveStart(APIArchivePreview):
    investigation_name: str = Field(default="Monarch Legacy Program", min_length=1, max_length=500)
    investigation_id: str | None = Field(default=None, max_length=100)
    transcribe_media: bool = True
    ocr_images: bool = False
    create_thumbnails: bool = True
    whisper_model: str = Field(default="small", max_length=100)
    whisper_device: str = Field(default="cpu", max_length=100)


class APIArchiveAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["pause", "resume", "cancel", "retry"]


class APIArchiveExtract(APIExtractionRetry):
    revision_id: str | None = Field(default=None, max_length=100)
    file_id: str | None = Field(default=None, max_length=100)
    chunk_size: int = Field(default=12000, ge=500, le=100000)
    overlap: int = Field(default=1000, ge=0, le=20000)
    max_chunks: int | None = Field(default=None, ge=1, le=10000)


def is_loopback_host_header(host: str) -> bool:
    try:
        return urlparse(f"//{host}").hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


def origin_allows_write(origin: str | None, port: int) -> bool:
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
        origin_port = parsed.port or (80 if parsed.scheme == "http" else None)
    except ValueError:
        return False
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS and origin_port == port


def validated_body_size(content_type: str, content_length: str | None,
                        transfer_encoding: str | None = None) -> int:
    if transfer_encoding:
        raise ValueError("transfer-encoded request bodies are not accepted")
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise ValueError("Content-Type must be application/json")
    if content_length is None:
        raise ValueError("Content-Length is required")
    try:
        size = int(content_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if size < 0 or size > MAX_BODY_BYTES:
        raise OverflowError(f"request body exceeds {MAX_BODY_BYTES} bytes")
    return size


def parse_json_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("malformed JSON body") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    return value


def _background_process(db_path: Path, job_id: str, provider, retry: bool = False) -> None:
    try:
        with VaultDB(db_path) as db:
            process_extraction_job(db, job_id, provider, retry_failed=retry)
    except Exception as exc:
        with VaultDB(db_path) as db:
            with db.transaction():
                db.conn.execute(
                    "UPDATE extraction_jobs SET status='failed',error=?,updated_at=datetime('now') WHERE id=?",
                    (str(exc)[:2000], job_id),
                )


def _background_import(db_path: Path, job_id: str) -> None:
    try:
        with VaultDB(db_path) as db:
            process_import_job(db, job_id)
    except Exception as exc:
        with VaultDB(db_path) as db:
            with db.transaction():
                db.conn.execute(
                    "UPDATE archive_import_jobs SET status='failed',error=?,updated_at=datetime('now') WHERE id=?",
                    (str(exc)[:2000], job_id),
                )


def handler_for(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _security_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")

        def _json(self, value: object, status: int = 200) -> None:
            data = json.dumps(value, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)

        def _bytes(self, data: bytes, content_type: str, status: int = 200,
                   disposition: str | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if disposition:
                self.send_header("Content-Disposition", disposition)
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)

        def _static(self, request_path: str) -> None:
            relative = "index.html" if request_path == "/" else request_path.removeprefix("/static/")
            candidate = (STATIC_ROOT / relative).resolve()
            if not candidate.is_relative_to(STATIC_ROOT.resolve()) or not candidate.is_file():
                self._json({"error": "not found"}, 404)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if candidate.suffix == ".js":
                content_type = "text/javascript"
            data = candidate.read_bytes()
            if content_type.startswith(("text/", "application/javascript")):
                data = data.replace(b"\r\n", b"\n")
            self._bytes(data, f"{content_type}; charset=utf-8" if content_type.startswith(("text/", "application/javascript")) else content_type)

        def _body(self) -> dict:
            size = validated_body_size(
                self.headers.get("Content-Type", ""), self.headers.get("Content-Length"),
                self.headers.get("Transfer-Encoding"),
            )
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("incomplete request body")
            return parse_json_object(raw)

        def _request_is_local(self, write: bool = False) -> bool:
            host = self.headers.get("Host", "")
            if not is_loopback_host_header(host):
                self._json({"error": "local Host header required"}, 403)
                return False
            if write:
                origin = self.headers.get("Origin")
                if not origin_allows_write(origin, self.server.server_address[1]):
                    self._json({"error": "cross-origin writes are forbidden"}, 403)
                    return False
            return True

        def _error(self, exc: Exception) -> None:
            if isinstance(exc, OverflowError):
                self._json({"error": str(exc)}, 413)
            elif isinstance(exc, sqlite3.IntegrityError):
                self._json({"error": "record violates a database constraint"}, 409)
            elif isinstance(exc, (ValueError, KeyError, json.JSONDecodeError)):
                self._json({"error": str(exc)}, 400)
            else:
                self.log_error("request failed: %s", exc)
                self._json({"error": "request failed"}, 500)

        def do_GET(self) -> None:  # noqa: N802
            if not self._request_is_local():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._static(parsed.path); return
            if parsed.path.startswith("/static/"):
                self._static(parsed.path); return
            try:
                with VaultDB(db_path) as db:
                    query = parse_qs(parsed.query)
                    if parsed.path == "/api/stats": result = db.stats()
                    elif parsed.path == "/api/review": result = db.list_review()
                    elif parsed.path == "/api/search":
                        term = query.get("q", [""])[0]
                        if len(term) > 500: raise ValueError("search query is too long")
                        result = db.search(term, query.get("type", [None])[0])
                    elif parsed.path == "/api/events": result = db.events_between(query.get("start", ["0001"])[0], query.get("end", ["9999"])[0])
                    elif parsed.path == "/api/graph":
                        result = graph_data(
                            db, focus_id=query.get("focus", [None])[0],
                            depth=int(query.get("depth", ["1"])[0]), query=query.get("q", [""])[0],
                            entity_types=set(filter(None, query.get("types", [""])[0].split(","))),
                            relationship_types=set(filter(None, query.get("relationships", [""])[0].split(","))),
                            investigation_ids=set(filter(None, query.get("investigations", [""])[0].split(","))),
                            start=query.get("start", [None])[0], end=query.get("end", [None])[0],
                            temporal_mode=query.get("temporal", ["all"])[0],
                            include_candidates=query.get("candidates", ["0"])[0] == "1",
                            include_documents=query.get("documents", ["0"])[0] == "1",
                            limit=int(query.get("limit", ["200"])[0]), cursor=query.get("cursor", [None])[0],
                        )
                    elif parsed.path == "/api/timeline":
                        result = timeline_data(
                            db, start=query.get("start", ["0001"])[0], end=query.get("end", ["9999"])[0],
                            entity_id=query.get("entity", [None])[0], event_type=query.get("event_type", [None])[0],
                            country=query.get("country", [None])[0], source_id=query.get("source", [None])[0],
                            investigation_ids=set(filter(None, query.get("investigations", [""])[0].split(","))),
                            limit=int(query.get("limit", ["200"])[0]), cursor=query.get("cursor", [None])[0],
                        )
                    elif parsed.path == "/api/paths":
                        result = connection_paths(
                            db, query.get("source", [""])[0], query.get("target", [""])[0],
                            max_depth=int(query.get("depth", ["4"])[0]),
                            relationship_types=set(filter(None, query.get("relationships", [""])[0].split(","))),
                            respect_direction=query.get("directed", ["0"])[0] == "1",
                            max_paths=int(query.get("limit", ["5"])[0]),
                        )
                    elif parsed.path == "/api/investigations":
                        result = investigations_data(
                            db, set(filter(None, query.get("selected", [""])[0].split(",")))
                        )
                    elif parsed.path == "/api/exports/timeline.csv":
                        payload = timeline_data(
                            db, start=query.get("start", ["0001"])[0], end=query.get("end", ["9999"])[0],
                            entity_id=query.get("entity", [None])[0], event_type=query.get("event_type", [None])[0],
                            country=query.get("country", [None])[0], source_id=query.get("source", [None])[0],
                            investigation_ids=set(filter(None, query.get("investigations", [""])[0].split(","))),
                            limit=500,
                        )
                        data = timeline_csv(payload).encode("utf-8-sig")
                        return self._bytes(data, "text/csv; charset=utf-8", disposition='attachment; filename="vault-timeline.csv"')
                    elif parsed.path.startswith("/api/profiles/"):
                        result = entity_profile(db, parsed.path.rsplit("/", 1)[1])
                        if result is None: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/relationships/") and parsed.path.endswith("/detail"):
                        relationship_id = parsed.path.strip("/").split("/")[2]
                        result = relationship_detail(db, relationship_id)
                        if result is None: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/entities/"):
                        result = db.get_entity(parsed.path.rsplit("/", 1)[1])
                        if result is None: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/documents/"):
                        result = db.get_document(parsed.path.rsplit("/", 1)[1])
                        if result is None: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/extractions/"):
                        parts = parsed.path.strip("/").split("/")
                        if len(parts) == 4 and parts[3] == "review":
                            result = extraction_review(db, parts[2])
                        elif len(parts) == 3:
                            result = extraction_status(db, parts[2])
                        else: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/archive-imports/"):
                        parts = parsed.path.strip("/").split("/")
                        if len(parts) == 5 and parts[3] == "reports":
                            name = parts[4]
                            path = report_path(db, parts[2], name)
                            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                            return self._bytes(path.read_bytes(), content_type, disposition=f'attachment; filename="{path.name}"')
                        if len(parts) == 3:
                            result = import_status(
                                db, parts[2],
                                media_type=query.get("type", [None])[0],
                                status=query.get("status", [None])[0],
                                folder=query.get("folder", [None])[0],
                            )
                        else: return self._json({"error": "not found"}, 404)
                    else: return self._json({"error": "not found"}, 404)
                self._json(result)
            except Exception as exc:
                self._error(exc)

        def do_POST(self) -> None:  # noqa: N802
            if not self._request_is_local(write=True):
                return
            try:
                body = self._body()
                with VaultDB(db_path) as db:
                    if self.path == "/api/entities":
                        item = APIEntity.model_validate(body)
                        result = {"id": db.add_entity(item.entity_type, item.name, aliases=item.aliases, description=item.description, details=item.details)}
                    elif self.path == "/api/claims":
                        item = APIClaim.model_validate(body)
                        result = {"id": db.add_claim(item.statement, original_wording=item.original_wording, claim_type=item.claim_type, status=item.status, entity_ids=item.entity_ids, historical_start=item.historical_start.model_dump(), historical_end=item.historical_end.model_dump())}
                    elif self.path == "/api/relationships":
                        item = APIRelationship.model_validate(body)
                        result = {"id": db.add_relationship(item.subject_id, item.object_id, item.relationship_type, directed=item.directed, classification=item.classification, historical_start=item.historical_start.model_dump(), historical_end=item.historical_end.model_dump())}
                    elif self.path == "/api/extractions":
                        item = APIExtractionStart.model_validate(body)
                        provider = build_provider(
                            item.provider, model=item.model, allow_cloud=item.allow_cloud,
                            manual_results=Path(item.manual_results) if item.manual_results else None,
                        )
                        job_id, created = create_extraction_job(
                            db, Path(item.document), provider,
                            config=ExtractionConfig(item.chunk_size, item.overlap, item.max_chunks),
                            allow_cloud=item.allow_cloud,
                        )
                        Thread(target=_background_process, args=(db_path, job_id, provider), daemon=True).start()
                        return self._json({"job_id": job_id, "created": created, "status": "processing"}, 202)
                    elif self.path == "/api/archive-imports/preview":
                        item = APIArchivePreview.model_validate(body)
                        result = preview_archive(Path(item.source))
                    elif self.path == "/api/archive-imports":
                        item = APIArchiveStart.model_validate(body)
                        config = ArchiveImportConfig(
                            transcribe_media=item.transcribe_media,
                            ocr_images=item.ocr_images,
                            create_thumbnails=item.create_thumbnails,
                            whisper_model=item.whisper_model,
                            whisper_device=item.whisper_device,
                        )
                        job_id, preview = create_import_job(
                            db, Path(item.source), investigation_name=item.investigation_name,
                            investigation_id=item.investigation_id, config=config,
                        )
                        Thread(target=_background_import, args=(db_path, job_id), daemon=True).start()
                        return self._json({"job_id": job_id, "status": "processing", "preview": preview}, 202)
                    elif self.path.startswith("/api/archive-imports/"):
                        parts = self.path.strip("/").split("/")
                        if len(parts) == 4 and parts[3] == "action":
                            item = APIArchiveAction.model_validate(body)
                            result = set_job_action(db, parts[2], item.action)
                            if item.action in {"resume", "retry"}:
                                Thread(target=_background_import, args=(db_path, parts[2]), daemon=True).start()
                            return self._json(result, 202)
                        if len(parts) == 4 and parts[3] == "extract":
                            item = APIArchiveExtract.model_validate(body)
                            revision_id = item.revision_id
                            if item.file_id:
                                row = db.conn.execute(
                                    "SELECT revision_id FROM archive_import_files WHERE job_id=? AND id=?",
                                    (parts[2], item.file_id),
                                ).fetchone()
                                if not row or not row[0]: raise ValueError("imported file has no extracted revision")
                                revision_id = row[0]
                            if not revision_id: raise ValueError("revision_id or file_id is required")
                            provider = build_provider(
                                item.provider, model=item.model, allow_cloud=item.allow_cloud,
                                manual_results=Path(item.manual_results) if item.manual_results else None,
                            )
                            extraction_id, created = create_extraction_job_from_revision(
                                db, revision_id, provider,
                                config=ExtractionConfig(item.chunk_size, item.overlap, item.max_chunks),
                                allow_cloud=item.allow_cloud,
                            )
                            Thread(target=_background_process, args=(db_path, extraction_id, provider), daemon=True).start()
                            return self._json({"job_id": extraction_id, "created": created, "status": "processing"}, 202)
                        return self._json({"error": "not found"}, 404)
                    elif self.path.startswith("/api/extractions/"):
                        parts = self.path.strip("/").split("/")
                        if len(parts) == 4 and parts[3] == "commit":
                            result = {"committed": commit_approved(db, parts[2])}
                        elif len(parts) == 4 and parts[3] == "retry":
                            item = APIExtractionRetry.model_validate(body)
                            provider = build_provider(
                                item.provider, model=item.model, allow_cloud=item.allow_cloud,
                                manual_results=Path(item.manual_results) if item.manual_results else None,
                            )
                            Thread(target=_background_process, args=(db_path, parts[2], provider, True), daemon=True).start()
                            return self._json({"job_id": parts[2], "status": "processing"}, 202)
                        else: return self._json({"error": "not found"}, 404)
                    else: return self._json({"error": "not found"}, 404)
                self._json(result, 201)
            except Exception as exc:
                self._error(exc)

        def do_PATCH(self) -> None:  # noqa: N802
            if not self._request_is_local(write=True):
                return
            try:
                body = self._body()
                with VaultDB(db_path) as db:
                    record_id = self.path.rsplit("/", 1)[1]
                    if self.path.startswith("/api/entities/"):
                        unknown = set(body) - {"canonical_name", "description"}
                        if unknown: raise ValueError(f"unsupported entity fields: {sorted(unknown)}")
                        db.update_entity(record_id, **body); result = db.get_entity(record_id)
                    elif self.path.startswith("/api/claims/"):
                        unknown = set(body) - {"statement", "original_wording", "claim_type", "epistemic_status", "historical_start", "historical_start_precision", "historical_start_certainty", "historical_end", "historical_end_precision", "historical_end_certainty"}
                        if unknown: raise ValueError(f"unsupported claim fields: {sorted(unknown)}")
                        db.update_claim(record_id, **body); result = {"id": record_id, "updated": True}
                    elif self.path.startswith("/api/relationships/"):
                        unknown = set(body) - {"relationship_type", "directed", "classification", "historical_start", "historical_start_precision", "historical_start_certainty", "historical_end", "historical_end_precision", "historical_end_certainty"}
                        if unknown: raise ValueError(f"unsupported relationship fields: {sorted(unknown)}")
                        db.update_relationship(record_id, **body); result = {"id": record_id, "updated": True}
                    elif self.path.startswith("/api/extractions/"):
                        parts = self.path.strip("/").split("/")
                        if len(parts) != 5 or parts[3] != "proposals":
                            return self._json({"error": "not found"}, 404)
                        item = APIProposalDecision.model_validate(body)
                        decide_proposal(db, parts[2], parts[4], item.action, known_entity_id=item.known_entity_id)
                        result = {"proposal_id": parts[4], "status": item.action}
                    else: return self._json({"error": "not found"}, 404)
                self._json(result)
            except Exception as exc:
                self._error(exc)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._json({"error": "cross-origin requests are not supported"}, 405)

        def log_message(self, format: str, *args: object) -> None:
            print(f"Vault: {format % args}")
    return Handler


def serve(db_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("the Vault server may bind only to localhost/loopback")
    server = ThreadingHTTPServer((host, port), handler_for(db_path))
    print(f"Vault browser: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
