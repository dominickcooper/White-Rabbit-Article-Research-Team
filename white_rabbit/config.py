from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    root: Path
    workspace: Path
    style_path: Path
    gemini_api_key: str
    model: str
    research_questions: int
    web_sources_per_query: int
    local_chunks: int
    max_evidence_items: int
    http_timeout: int
    sitemap_url: str
    substack_url: str = ""
    archive_sync_before_run: bool = True
    archive_plan_chunks: int = 10
    archive_writer_articles: int = 6
    archive_request_delay_ms: int = 120

    @property
    def research_library(self) -> Path:
        return self.root / "research_library"

    @property
    def archive_root(self) -> Path:
        return self.research_library / "previous_white_rabbit_articles"

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge"

    @property
    def archive_db_path(self) -> Path:
        return self.knowledge_dir / "white_rabbit.db"

    @property
    def project_sources_root(self) -> Path:
        return self.research_library / "projects"


def load_settings(root: Path | None = None) -> Settings:
    root = (root or Path.cwd()).resolve()
    load_dotenv(root / ".env")

    return Settings(
        root=root,
        workspace=root / "workspace",
        style_path=root / "config" / "white_rabbit_style.md",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("WR_MODEL", "gemini-3.7-flash").strip(),
        research_questions=max(1, int(os.getenv("WR_RESEARCH_QUESTIONS", "8"))),
        web_sources_per_query=max(1, int(os.getenv("WR_WEB_SOURCES_PER_QUERY", "3"))),
        local_chunks=max(1, int(os.getenv("WR_LOCAL_CHUNKS", "20"))),
        max_evidence_items=max(10, int(os.getenv("WR_MAX_EVIDENCE_ITEMS", "120"))),
        http_timeout=max(5, int(os.getenv("WR_HTTP_TIMEOUT", "30"))),
        sitemap_url=os.getenv("WR_WHITE_RABBIT_SITEMAP_URL", "").strip(),
        substack_url=os.getenv("WR_SUBSTACK_URL", "").strip().rstrip("/"),
        archive_sync_before_run=_bool_env("WR_ARCHIVE_SYNC_BEFORE_RUN", True),
        archive_plan_chunks=max(1, int(os.getenv("WR_ARCHIVE_PLAN_CHUNKS", "10"))),
        archive_writer_articles=max(1, int(os.getenv("WR_ARCHIVE_WRITER_ARTICLES", "6"))),
        archive_request_delay_ms=max(0, int(os.getenv("WR_ARCHIVE_REQUEST_DELAY_MS", "120"))),
    )
