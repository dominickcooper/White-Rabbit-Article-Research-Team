from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def resolve_archive_dir(local_dir: str, db_path: Path) -> Path:
    """Recover a moved standard archive path without changing persisted provenance."""
    original = Path(local_dir)
    root = Path(db_path).resolve().parent.parent
    # Handle historical Windows separators on every platform, and only recognize
    # the full archive suffix, never guess by basename/slug.
    parts = local_dir.replace("\\", "/").split("/")
    marker = ["research_library", "previous_white_rabbit_articles"]
    for index in range(len(parts) - 1):
        if [p.lower() for p in parts[index:index + 2]] == marker:
            suffix = parts[index + 2:]
            if any(p in {"", ".", ".."} or ":" in p for p in suffix):
                return original
            archive = root.joinpath(*marker).resolve()
            candidate = archive.joinpath(*suffix).resolve()
            if candidate.is_relative_to(archive) and (candidate / "article.md").is_file():
                return candidate
    if original.is_absolute() and (original / "article.md").is_file():
        return original
    # A repository-relative stored path must not depend on the caller's cwd.
    if not original.is_absolute() and not re_windows_absolute(local_dir):
        candidate = (root / original).resolve()
        if candidate.is_relative_to(root) and (candidate / "article.md").is_file():
            return candidate
    return original


def re_windows_absolute(value: str) -> bool:
    return len(value) >= 2 and value[1] == ":" or value.startswith("\\\\")


@dataclass(frozen=True)
class ArchiveArticle:
    wr_id: str
    title: str
    slug: str
    canonical_url: str
    published_date: Optional[str]
    author: Optional[str]
    content_hash: str
    content_status: str
    local_dir: str
    word_count: int
    last_seen: str
    last_synced: str


class ArchiveDB:
    """Persistent registry for previously published White Rabbit articles.

    This database is intentionally separate from per-project evidence databases.
    Prior White Rabbit articles are institutional memory / research leads, not
    automatically evidence for a new article.
    """

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
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS wr_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wr_id TEXT UNIQUE,
                title TEXT NOT NULL,
                slug TEXT NOT NULL,
                canonical_url TEXT NOT NULL UNIQUE,
                published_date TEXT,
                author TEXT,
                content_hash TEXT NOT NULL,
                content_status TEXT NOT NULL DEFAULT 'full',
                local_dir TEXT NOT NULL,
                word_count INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT NOT NULL,
                last_synced TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wr_article_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                anchor TEXT NOT NULL,
                url TEXT NOT NULL,
                link_kind TEXT NOT NULL DEFAULT 'external',
                FOREIGN KEY(article_id) REFERENCES wr_articles(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_wr_links_url ON wr_article_links(url);
            CREATE INDEX IF NOT EXISTS idx_wr_articles_slug ON wr_articles(slug);
            """
        )
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_by_url(self, canonical_url: str) -> ArchiveArticle | None:
        row = self.conn.execute(
            "SELECT * FROM wr_articles WHERE canonical_url = ?", (canonical_url,)
        ).fetchone()
        return self._to_article(row) if row else None

    def upsert_article(
        self,
        *,
        title: str,
        slug: str,
        canonical_url: str,
        published_date: str | None,
        author: str | None,
        content_hash: str,
        content_status: str,
        local_dir: str,
        word_count: int,
    ) -> tuple[ArchiveArticle, bool, bool]:
        """Return (article, created, content_changed)."""
        now = self._now()
        existing = self.conn.execute(
            "SELECT * FROM wr_articles WHERE canonical_url = ?", (canonical_url,)
        ).fetchone()
        if existing:
            changed = existing["content_hash"] != content_hash or existing["content_status"] != content_status
            self.conn.execute(
                """
                UPDATE wr_articles
                   SET title = ?, slug = ?, published_date = ?, author = ?,
                       content_hash = ?, content_status = ?, local_dir = ?,
                       word_count = ?, last_seen = ?, last_synced = ?
                 WHERE id = ?
                """,
                (
                    title, slug, published_date, author, content_hash,
                    content_status, local_dir, int(word_count), now, now,
                    int(existing["id"]),
                ),
            )
            self.conn.commit()
            return self.get_by_url(canonical_url), False, changed  # type: ignore[return-value]

        cur = self.conn.execute(
            """
            INSERT INTO wr_articles(
                wr_id, title, slug, canonical_url, published_date, author,
                content_hash, content_status, local_dir, word_count,
                last_seen, last_synced
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title, slug, canonical_url, published_date, author,
                content_hash, content_status, local_dir, int(word_count), now, now,
            ),
        )
        row_id = int(cur.lastrowid)
        wr_id = f"WR-{row_id:06d}"
        self.conn.execute("UPDATE wr_articles SET wr_id = ? WHERE id = ?", (wr_id, row_id))
        self.conn.commit()
        return self.get_by_url(canonical_url), True, True  # type: ignore[return-value]

    def mark_seen(self, canonical_url: str) -> None:
        self.conn.execute(
            "UPDATE wr_articles SET last_seen = ? WHERE canonical_url = ?",
            (self._now(), canonical_url),
        )
        self.conn.commit()

    def replace_links(self, canonical_url: str, links: list[dict]) -> None:
        row = self.conn.execute(
            "SELECT id FROM wr_articles WHERE canonical_url = ?", (canonical_url,)
        ).fetchone()
        if not row:
            raise KeyError(f"Unknown archive article: {canonical_url}")
        article_id = int(row["id"])
        self.conn.execute("DELETE FROM wr_article_links WHERE article_id = ?", (article_id,))
        for link in links:
            anchor = str(link.get("anchor", "")).strip()
            url = str(link.get("url", "")).strip()
            if not anchor or not url:
                continue
            self.conn.execute(
                "INSERT INTO wr_article_links(article_id, anchor, url, link_kind) VALUES (?, ?, ?, ?)",
                (article_id, anchor, url, str(link.get("type", "external"))),
            )
        self.conn.commit()

    def list_articles(self) -> list[ArchiveArticle]:
        rows = self.conn.execute(
            "SELECT * FROM wr_articles ORDER BY COALESCE(published_date, '') DESC, id DESC"
        ).fetchall()
        return [self._to_article(r) for r in rows]

    def links_for(self, canonical_url: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT l.anchor, l.url, l.link_kind
              FROM wr_article_links l
              JOIN wr_articles a ON a.id = l.article_id
             WHERE a.canonical_url = ?
             ORDER BY l.id
            """,
            (canonical_url,),
        ).fetchall()
        return [{"anchor": r["anchor"], "url": r["url"], "type": r["link_kind"]} for r in rows]

    def status(self) -> dict:
        total = int(self.conn.execute("SELECT COUNT(*) c FROM wr_articles").fetchone()["c"])
        preview = int(self.conn.execute(
            "SELECT COUNT(*) c FROM wr_articles WHERE content_status = 'preview_only'"
        ).fetchone()["c"])
        full = int(self.conn.execute(
            "SELECT COUNT(*) c FROM wr_articles WHERE content_status = 'full'"
        ).fetchone()["c"])
        links = int(self.conn.execute("SELECT COUNT(*) c FROM wr_article_links").fetchone()["c"])
        return {"articles": total, "full": full, "preview_only": preview, "links": links}

    def _to_article(self, row: sqlite3.Row) -> ArchiveArticle:
        return ArchiveArticle(
            wr_id=row["wr_id"], title=row["title"], slug=row["slug"],
            canonical_url=row["canonical_url"], published_date=row["published_date"],
            author=row["author"], content_hash=row["content_hash"],
            content_status=row["content_status"], local_dir=str(resolve_archive_dir(row["local_dir"], self.path)),
            word_count=int(row["word_count"]), last_seen=row["last_seen"],
            last_synced=row["last_synced"],
        )
