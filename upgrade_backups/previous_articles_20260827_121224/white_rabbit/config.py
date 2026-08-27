from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


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
    )
