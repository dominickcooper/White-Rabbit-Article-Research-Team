from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .schemas import ExtractedEvidence


@dataclass
class SourceRecord:
    id: int
    title: str
    source_kind: str
    url: Optional[str]
    file_path: Optional[str]
    reliability: str


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_id: int
    claim: str
    excerpt: Optional[str]
    excerpt_verified: bool
    support_type: str
    reliability: str
    entities: list[str]
    significance: str
    published_date: Optional[str]
    author: Optional[str]


class EvidenceDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                url TEXT,
                file_path TEXT,
                reliability TEXT NOT NULL DEFAULT 'unknown',
                UNIQUE(url),
                UNIQUE(file_path)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT UNIQUE,
                source_id INTEGER NOT NULL,
                claim TEXT NOT NULL,
                excerpt TEXT,
                excerpt_verified INTEGER NOT NULL DEFAULT 0,
                support_type TEXT NOT NULL,
                reliability TEXT NOT NULL,
                entities_json TEXT NOT NULL DEFAULT '[]',
                significance TEXT NOT NULL DEFAULT '',
                published_date TEXT,
                author TEXT,
                FOREIGN KEY(source_id) REFERENCES sources(id)
            );
            CREATE TABLE IF NOT EXISTS research_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT,
                query TEXT,
                notes TEXT,
                citations_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        self.conn.commit()

    def add_source(
        self,
        *,
        title: str,
        source_kind: str,
        url: str | None = None,
        file_path: str | None = None,
        reliability: str = "unknown",
    ) -> int:
        if not url and not file_path:
            raise ValueError("Source requires url or file_path")
        if url:
            row = self.conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
        else:
            row = self.conn.execute("SELECT id FROM sources WHERE file_path = ?", (file_path,)).fetchone()
        if row:
            return int(row["id"])
        cur = self.conn.execute(
            "INSERT INTO sources(title, source_kind, url, file_path, reliability) VALUES (?, ?, ?, ?, ?)",
            (title or "Untitled source", source_kind, url, file_path, reliability),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_research_run(self, question_id: str, query: str, notes: str, citations: list[dict]) -> None:
        self.conn.execute(
            "INSERT INTO research_runs(question_id, query, notes, citations_json) VALUES (?, ?, ?, ?)",
            (question_id, query, notes, json.dumps(citations, ensure_ascii=False)),
        )
        self.conn.commit()

    def add_evidence(
        self,
        source_id: int,
        item: ExtractedEvidence,
        *,
        excerpt_verified: bool,
    ) -> str:
        # Avoid obvious duplicates from repeated queries hitting the same source.
        dup = self.conn.execute(
            "SELECT evidence_id FROM evidence WHERE source_id = ? AND lower(claim) = lower(?)",
            (source_id, item.claim.strip()),
        ).fetchone()
        if dup:
            return str(dup["evidence_id"])
        cur = self.conn.execute(
            """
            INSERT INTO evidence(
                evidence_id, source_id, claim, excerpt, excerpt_verified,
                support_type, reliability, entities_json, significance,
                published_date, author
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                item.claim.strip(),
                item.excerpt,
                1 if excerpt_verified else 0,
                item.support_type,
                item.reliability,
                json.dumps(item.entities, ensure_ascii=False),
                item.significance,
                item.published_date,
                item.author,
            ),
        )
        row_id = int(cur.lastrowid)
        evidence_id = f"EV-{row_id:04d}"
        self.conn.execute("UPDATE evidence SET evidence_id = ? WHERE id = ?", (evidence_id, row_id))
        self.conn.commit()
        return evidence_id

    def list_sources(self) -> list[SourceRecord]:
        rows = self.conn.execute("SELECT * FROM sources ORDER BY id").fetchall()
        return [
            SourceRecord(
                id=int(r["id"]), title=r["title"], source_kind=r["source_kind"],
                url=r["url"], file_path=r["file_path"], reliability=r["reliability"]
            )
            for r in rows
        ]

    def list_evidence(self, limit: int | None = None) -> list[EvidenceRecord]:
        sql = "SELECT * FROM evidence ORDER BY id"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        rows = self.conn.execute(sql, params).fetchall()
        return [
            EvidenceRecord(
                evidence_id=r["evidence_id"], source_id=int(r["source_id"]), claim=r["claim"],
                excerpt=r["excerpt"], excerpt_verified=bool(r["excerpt_verified"]),
                support_type=r["support_type"], reliability=r["reliability"],
                entities=json.loads(r["entities_json"] or "[]"), significance=r["significance"],
                published_date=r["published_date"], author=r["author"],
            )
            for r in rows
        ]

    def evidence_lookup(self) -> dict[str, tuple[EvidenceRecord, SourceRecord]]:
        sources = {s.id: s for s in self.list_sources()}
        return {e.evidence_id: (e, sources[e.source_id]) for e in self.list_evidence()}

    def build_packet(self, limit: int = 120) -> str:
        lookup = self.evidence_lookup()
        parts: list[str] = []
        for evidence_id, (e, s) in list(lookup.items())[:limit]:
            parts.append(f"### {evidence_id}\n")
            parts.append(f"Claim: {e.claim}\n")
            parts.append(f"Support: {e.support_type}; Reliability: {e.reliability}\n")
            parts.append(f"Source: {s.title}\n")
            if s.url:
                parts.append(f"URL: {s.url}\n")
            if s.file_path:
                parts.append(f"Private file: {s.file_path}\n")
            if e.published_date:
                parts.append(f"Date: {e.published_date}\n")
            if e.author:
                parts.append(f"Author: {e.author}\n")
            if e.excerpt:
                verified = "VERIFIED" if e.excerpt_verified else "UNVERIFIED"
                parts.append(f"Excerpt ({verified}): {e.excerpt[:900]}\n")
            if e.entities:
                parts.append(f"Entities: {', '.join(e.entities[:15])}\n")
            if e.significance:
                parts.append(f"Why it matters: {e.significance}\n")
            parts.append("\n")
        return "".join(parts)
