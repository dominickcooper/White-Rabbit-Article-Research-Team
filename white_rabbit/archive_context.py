from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .archive_retrieval import ArchiveMemory, format_archive_memory, retrieve_archive_memory
from .archive_voice import VoiceSearchResult, format_voice_reference_packet, retrieve_voice_references


@dataclass(frozen=True)
class ArchiveContext:
    canon_memories: tuple[ArchiveMemory, ...]
    voice_result: VoiceSearchResult
    canon_packet: str
    voice_packet: str

    @property
    def combined_packet(self) -> str:
        return self.canon_packet + "\n\n" + self.voice_packet


def build_archive_context(
    *,
    root: Path,
    db_path: Path,
    query: str,
    canon_articles: int = 6,
    voice_passages: int = 8,
) -> ArchiveContext:
    db_path = Path(db_path)
    if db_path.is_file():
        memories = retrieve_archive_memory(
            db_path,
            query=query,
            article_limit=canon_articles,
            chunk_limit=max(12, canon_articles * 3),
            min_score=0.0,
        )
    else:
        memories = []
    voice = retrieve_voice_references(
        db_path,
        query,
        root=root,
        passage_limit=voice_passages,
    )
    return ArchiveContext(
        canon_memories=tuple(memories),
        voice_result=voice,
        canon_packet=format_archive_memory(memories),
        voice_packet=format_voice_reference_packet(voice),
    )
