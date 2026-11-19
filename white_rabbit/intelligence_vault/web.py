from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field

from .database import VaultDB
from .schema import TemporalValue


MAX_BODY_BYTES = 256 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


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


INDEX = """<!doctype html><html><head><meta charset='utf-8'><title>White Rabbit Intelligence Vault</title>
<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem;background:#111;color:#eee}
input,select,button{font:inherit;padding:.55rem;margin:.2rem}button{cursor:pointer}a{color:#a9d5ff}
pre{white-space:pre-wrap;background:#1d1d1d;padding:1rem;border-radius:8px}.row{display:flex;gap:1rem;flex-wrap:wrap}</style></head>
<body><h1>White Rabbit Intelligence Vault</h1><p>Provenance-first local historical research.</p>
<div><input id='q' size='45' placeholder='Search entities, claims, documents'><button onclick='search()'>Search</button>
<button onclick='stats()'>Statistics</button><button onclick='review()'>Review queue</button></div>
<h2>Add entity</h2><div class='row'><select id='type'><option>person</option><option>organization</option><option>event</option><option>place</option></select>
<input id='name' placeholder='Canonical name'><input id='aliases' placeholder='Aliases, comma separated'><button onclick='addEntity()'>Add</button></div>
<pre id='out'>Ready.</pre><script>
const out=document.querySelector('#out'); async function call(url,opts){let r=await fetch(url,opts);let j=await r.json();out.textContent=JSON.stringify(j,null,2)}
function search(){call('/api/search?q='+encodeURIComponent(q.value))} function stats(){call('/api/stats')} function review(){call('/api/review')}
function addEntity(){call('/api/entities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entity_type:type.value,name:name.value,aliases:aliases.value.split(',').map(x=>x.trim()).filter(Boolean)})})}
</script></body></html>"""


def handler_for(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _security_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")

        def _json(self, value: object, status: int = 200) -> None:
            data = json.dumps(value, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)

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
                data = INDEX.encode()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data))); self._security_headers()
                self.end_headers(); self.wfile.write(data); return
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
                    elif parsed.path.startswith("/api/entities/"):
                        result = db.get_entity(parsed.path.rsplit("/", 1)[1])
                        if result is None: return self._json({"error": "not found"}, 404)
                    elif parsed.path.startswith("/api/documents/"):
                        result = db.get_document(parsed.path.rsplit("/", 1)[1])
                        if result is None: return self._json({"error": "not found"}, 404)
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
