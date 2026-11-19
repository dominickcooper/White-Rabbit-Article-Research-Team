from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .database import VaultDB


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
        def _json(self, value: object, status: int = 200) -> None:
            data = json.dumps(value, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            size = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(size) or b"{}")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                data = INDEX.encode()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            try:
                with VaultDB(db_path) as db:
                    query = parse_qs(parsed.query)
                    if parsed.path == "/api/stats": result = db.stats()
                    elif parsed.path == "/api/review": result = db.list_review()
                    elif parsed.path == "/api/search": result = db.search(query.get("q", [""])[0], query.get("type", [None])[0])
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
                self._json({"error": str(exc)}, 400)

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._body()
                with VaultDB(db_path) as db:
                    if self.path == "/api/entities":
                        result = {"id": db.add_entity(body["entity_type"], body["name"], aliases=body.get("aliases"), description=body.get("description", ""), details=body.get("details"))}
                    elif self.path == "/api/claims":
                        result = {"id": db.add_claim(body["statement"], original_wording=body.get("original_wording"), claim_type=body.get("claim_type", "fact"), status=body.get("status", "DOCUMENTED RECORD"), entity_ids=body.get("entity_ids"))}
                    elif self.path == "/api/relationships":
                        result = {"id": db.add_relationship(body["subject_id"], body["object_id"], body["relationship_type"], directed=body.get("directed", True), classification=body.get("classification", "DOCUMENTED RECORD"), historical_start=body.get("historical_start"), historical_end=body.get("historical_end"))}
                    else: return self._json({"error": "not found"}, 404)
                self._json(result, 201)
            except Exception as exc:
                self._json({"error": str(exc)}, 400)

        def do_PATCH(self) -> None:  # noqa: N802
            try:
                body = self._body()
                with VaultDB(db_path) as db:
                    record_id = self.path.rsplit("/", 1)[1]
                    if self.path.startswith("/api/entities/"):
                        db.update_entity(record_id, **body); result = db.get_entity(record_id)
                    elif self.path.startswith("/api/claims/"):
                        db.update_claim(record_id, **body); result = {"id": record_id, "updated": True}
                    elif self.path.startswith("/api/relationships/"):
                        db.update_relationship(record_id, **body); result = {"id": record_id, "updated": True}
                    else: return self._json({"error": "not found"}, 404)
                self._json(result)
            except Exception as exc:
                self._json({"error": str(exc)}, 400)

        def log_message(self, format: str, *args: object) -> None:
            print(f"Vault: {format % args}")
    return Handler


def serve(db_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), handler_for(db_path))
    print(f"Vault browser: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
