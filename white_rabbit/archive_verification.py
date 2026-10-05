from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .archive_context import build_archive_context
from .archive_db import ArchiveDB
from .archive_retrieval import retrieve_archive_memory
from .archive_voice import retrieve_voice_references


INVENTORY_FIELDS = (
    "article_id", "canonical_url", "title", "published_timestamp", "updated_timestamp",
    "year", "series", "tags", "paywall_state", "access_level", "source_origin",
    "export_post_id", "publication_status", "audience", "source_reference",
    "discovery_sources", "http_status", "word_count", "author_paragraph_count",
    "content_hash", "archive_path", "indexed", "failure_reason",
    "publication_review_status", "duplicate_of",
)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _access(metadata: dict, content_status: str) -> str:
    value = str(metadata.get("access_level") or "").strip()
    if value:
        return value
    origin = str(metadata.get("source_origin") or "")
    if origin == "author_export":
        return "FULL_AUTHOR_EXPORT"
    return "PARTIAL_PREVIEW" if content_status == "preview_only" else "FULL_PUBLIC"


def build_inventory(archive_root: Path, db_path: Path) -> list[dict[str, object]]:
    archive_root = Path(archive_root)
    sync_report = _load_json(archive_root / "sync" / "sync_report.json")
    failures = {str(row.get("url")): row for row in sync_report.get("errors", [])}
    missing = {str(row.get("url")) for row in sync_report.get("missing_from_latest_discovery", [])}
    db = ArchiveDB(db_path)
    try:
        articles = db.list_articles()
    finally:
        db.close()
    rows: list[dict[str, object]] = []
    first_hash: dict[str, str] = {}
    for article in sorted(articles, key=lambda item: item.canonical_url):
        local_dir = Path(article.local_dir)
        metadata = _load_json(local_dir / "metadata.json")
        published = str(metadata.get("published_date") or article.published_date or "")
        year_match = re.match(r"(20\d{2})", published)
        year = year_match.group(1) if year_match else "UNKNOWN"
        content_hash = str(metadata.get("content_hash") or f"sha256:{article.content_hash}")
        raw_hash = content_hash.removeprefix("sha256:")
        duplicate_of = first_hash.get(raw_hash, "")
        first_hash.setdefault(raw_hash, article.canonical_url)
        access = _access(metadata, article.content_status)
        failure = failures.get(article.canonical_url)
        if failure:
            access = "FETCH_FAILED"
        rows.append({
            "article_id": article.wr_id,
            "canonical_url": article.canonical_url,
            "title": article.title,
            "published_timestamp": published,
            "updated_timestamp": metadata.get("updated_date") or "",
            "year": year,
            "series": metadata.get("series") or "",
            "tags": "|".join(str(x) for x in metadata.get("tags", [])),
            "paywall_state": (
                "paid_or_subscriber_preview" if access == "PARTIAL_PREVIEW"
                else "title_only" if access == "TITLE_ONLY"
                else "public_or_owner_full"
            ),
            "access_level": access,
            "source_origin": metadata.get("source_origin") or "public_web",
            "export_post_id": metadata.get("export_post_id") or "",
            "publication_status": metadata.get("publication_status") or "published",
            "audience": metadata.get("audience") or "",
            "source_reference": metadata.get("source_reference") or "",
            "discovery_sources": "|".join(str(x) for x in metadata.get("discovery_sources", [])),
            "http_status": metadata.get("http_status") or "",
            "word_count": int(metadata.get("word_count") or article.word_count or 0),
            "author_paragraph_count": metadata.get("author_paragraph_count") if metadata.get("author_paragraph_count") is not None else "",
            "content_hash": content_hash,
            "archive_path": str(local_dir / "article.md"),
            "indexed": str(bool(metadata.get("indexed", True)) and not failure).lower(),
            "failure_reason": (failure or {}).get("error", ""),
            "publication_review_status": "MISSING_FROM_LATEST_DISCOVERY" if article.canonical_url in missing else "CURRENT",
            "duplicate_of": duplicate_of,
        })
    known = {str(row["canonical_url"]) for row in rows}
    for url, failure in sorted(failures.items()):
        if url in known:
            continue
        rows.append({
            "article_id": "", "canonical_url": url, "title": "",
            "published_timestamp": "", "updated_timestamp": "", "year": "UNKNOWN",
            "series": "", "tags": "", "paywall_state": "unknown",
            "access_level": "FETCH_FAILED", "source_origin": "public_web",
            "export_post_id": "", "publication_status": "published",
            "audience": "", "source_reference": "",
            "discovery_sources": "|".join(failure.get("discovery_sources", [])),
            "http_status": failure.get("http_status") or "", "word_count": 0,
            "author_paragraph_count": 0, "content_hash": "", "archive_path": "",
            "indexed": "false", "failure_reason": failure.get("error") or "fetch failed",
            "publication_review_status": "CURRENT", "duplicate_of": "",
        })
    return sorted(rows, key=lambda row: (str(row["published_timestamp"]), str(row["canonical_url"])), reverse=True)


def write_inventory(archive_root: Path, db_path: Path) -> tuple[Path, list[dict[str, object]]]:
    rows = build_inventory(archive_root, db_path)
    path = Path(archive_root) / "PUBLISHED_ARTICLE_INVENTORY.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path, rows


def _by_year(rows: list[dict[str, object]]) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        result[str(row["year"])][str(row["access_level"])] += 1
        result[str(row["year"])]["DISCOVERED"] += 1
    return dict(sorted(result.items()))


def _examples(rows: list[dict[str, object]], limit: int = 6) -> list[dict[str, object]]:
    usable = [row for row in rows if row["access_level"] != "FETCH_FAILED" and row["archive_path"]]
    picked: list[dict[str, object]] = []
    for year in ("2024", "2025", "2026"):
        candidates = [row for row in usable if row["year"] == year]
        if candidates:
            picked.append(max(candidates, key=lambda row: int(row["word_count"])))
    for access in ("PARTIAL_PREVIEW", "FULL_AUTHOR_EXPORT", "FULL_PUBLIC"):
        candidates = [row for row in usable if row["access_level"] == access and row not in picked]
        if candidates:
            picked.append(max(candidates, key=lambda row: int(row["word_count"])))
    for row in sorted(usable, key=lambda item: int(item["word_count"]), reverse=True):
        if row not in picked:
            picked.append(row)
        if len(picked) >= limit:
            break
    return picked[:limit]


def _excerpt(path: Path, limit: int = 360) -> str:
    text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def _gold_rows(root: Path, rows: list[dict[str, object]]) -> list[tuple[dict, dict | None]]:
    gold_path = root / "research_library" / "editorial_memory" / "GOLD_ARTICLES.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.is_file() else []
    matched: list[tuple[dict, dict | None]] = []
    for item in gold:
        title_tokens = set(re.findall(r"[a-z0-9]+", str(item.get("title", "")).casefold().replace("’s", "").replace("'s", "")))
        def title_score(row: dict[str, object]) -> float:
            candidate = set(re.findall(r"[a-z0-9]+", str(row["title"]).casefold().replace("’s", "").replace("'s", "")))
            overlap = title_tokens & candidate
            return len(overlap) / max(1, len(title_tokens))
        scored = sorted(((title_score(r), r) for r in rows), key=lambda pair: pair[0], reverse=True)
        row = scored[0][1] if scored and scored[0][0] >= 0.4 else None
        matched.append((item, row))
    return matched


def verify_archive(root: Path, archive_root: Path, db_path: Path) -> dict:
    root = Path(root)
    archive_root = Path(archive_root)
    inventory_path, rows = write_inventory(archive_root, db_path)
    sync = _load_json(archive_root / "sync" / "sync_report.json")
    probe = _load_json(archive_root / "sync" / "discovery_probe.json")
    export_report = _load_json(archive_root / "sync" / "author_export_import_report.json")
    endpoint_record = probe or sync
    years = _by_year(rows)
    examples = _examples(rows)

    coverage_lines = [
        "# White Rabbit Archive Coverage Report\n",
        "Generated from the SQLite registry, stored article bodies, and the latest live sync report. "
        "A URL listing is not counted as a full read.\n",
        "## Endpoint reachability\n",
        f"- Publication: {sync.get('publication_url', '')}\n",
        f"- Sitemap endpoints reached at HTTP level: {', '.join(endpoint_record.get('sitemap_urls_reached', [])) or 'not recorded'}\n",
        f"- Sitemap parse/fetch failures: {json.dumps(endpoint_record.get('sitemap_urls_failed', {}), ensure_ascii=False)}\n",
        f"- Latest discovery count: {endpoint_record.get('discovered', sync.get('discovered', len(rows)))}\n",
        "\n## Coverage by publication year and honest access level\n\n",
        "| Year | Discovered | Full public | Full author export | Partial preview | Title only | Fetch failed |\n",
        "|---|---:|---:|---:|---:|---:|---:|\n",
    ]
    for year, counts in years.items():
        coverage_lines.append(
            f"| {year} | {counts['DISCOVERED']} | {counts['FULL_PUBLIC']} | "
            f"{counts['FULL_AUTHOR_EXPORT']} | {counts['PARTIAL_PREVIEW']} | "
            f"{counts['TITLE_ONLY']} | {counts['FETCH_FAILED']} |\n"
        )
    coverage_lines.extend(["\n## Six body-text extraction proofs\n"])
    for row in examples:
        path = Path(str(row["archive_path"]))
        actual_hash = hashlib.sha256(path.read_text(encoding="utf-8-sig").rstrip("\n").encode("utf-8")).hexdigest() if path.is_file() else "MISSING"
        coverage_lines.extend([
            f"\n### {row['title']}\n",
            f"- Canonical URL: {row['canonical_url']}\n",
            f"- Access: {row['access_level']}\n",
            f"- Published: {row['published_timestamp']}\n",
            f"- Word count: {row['word_count']}\n",
            f"- Authored paragraph count: {row['author_paragraph_count']}\n",
            f"- Stored hash: {row['content_hash']}\n",
            f"- Recomputed body hash: sha256:{actual_hash}\n",
            f"- Archive body: `{row['archive_path']}`\n",
            f"- Body-text proof: {_excerpt(path)}\n",
        ])
    coverage_lines.extend(["\n## Gold/voice exemplar availability\n"])
    for gold, row in _gold_rows(root, rows):
        local = root / str(gold.get("path", ""))
        local_note = "FULL LOCAL AUTHOR FILE" if local.is_file() else "local file missing"
        if row:
            coverage_lines.append(
                f"- {gold.get('title')}: published archive {row['access_level']} "
                f"({row['canonical_url']}); {local_note} at `{gold.get('path')}`.\n"
            )
        else:
            status = "FULL LOCAL AUTHOR FILE (not automatically labeled published)" if local.is_file() else "MISSING"
            coverage_lines.append(f"- {gold.get('title')}: {status}; `{gold.get('path')}`\n")
    part7_hits = [row for row in rows if "part-7" in str(row["canonical_url"]).casefold() or "what survived inside foreign aid" in str(row["title"]).casefold()]
    coverage_lines.extend([
        "\n## Author-export reconciliation\n",
        f"- Export manifest rows: {export_report.get('manifest_rows', 'not recorded')}.\n",
        f"- Published rows imported: {export_report.get('published_rows', 'not recorded')}.\n",
        f"- Unpublished drafts excluded: {export_report.get('unpublished_rows_excluded', 'not recorded')}.\n",
        f"- Public paid previews repaired: {export_report.get('summary', {}).get('repaired_partial_previews', 'not recorded')}.\n",
        f"- Full author-export bodies: {export_report.get('summary', {}).get('full_author_export', 'not recorded')}.\n",
        f"- Title-only after export: {export_report.get('summary', {}).get('title_only_after_export', 'not recorded')}.\n",
        f"- New published posts absent from prior discovery: {export_report.get('summary', {}).get('new_published', 'not recorded')}.\n",
        f"- Private/account files ignored: {export_report.get('private_entries_ignored', 'not recorded')}; "
        f"open/delivery analytics ignored: {export_report.get('analytics_entries_ignored', 'not recorded')}.\n",
        "\n## Published-status guard\n",
        f"- Part 7 published-canon matches in live inventory: {len(part7_hits)}. "
        "The local Part 7 manuscript is not promoted into the published archive.\n",
        "\n## Missing-content conclusion\n",
        f"- Remaining partial/title-only posts: {sum(1 for row in rows if row['access_level'] in {'PARTIAL_PREVIEW', 'TITLE_ONLY'})}.\n",
        "- Import directly from the owner ZIP with `python -m white_rabbit archive import-export PATH_TO_EXPORT.zip`; only published post HTML is read. Subscriber, email, payment, pledge, open, and delivery files are ignored.\n",
    ])
    coverage_path = archive_root / "ARCHIVE_COVERAGE_REPORT.md"
    coverage_path.write_text("".join(coverage_lines), encoding="utf-8")

    queries = (
        "Jeffrey Epstein / Acosta / intelligence",
        "Robert Maxwell / Mossad",
        "Adnan Khashoggi / Safari Club",
        "Southern Air Transport / Iran-Contra",
        "CIA / OPS / International Police Services",
        "Project TWO-FOLD",
        "Operation Gladio",
        "Osama bin Laden",
        "International Syndicate",
    )
    canon_lines = ["# Canon Retrieval Smoke Test\n\n"]
    for query in queries:
        hits = retrieve_archive_memory(db_path, query=query, article_limit=3, chunk_limit=12, min_score=0.0)
        canon_lines.append(f"## Query: {query}\n")
        if not hits:
            canon_lines.append("No grounded archive hit.\n\n")
            continue
        for index, hit in enumerate(hits, 1):
            hit_metadata = _load_json(Path(hit.article.local_dir) / "metadata.json")
            access = _access(hit_metadata, hit.article.content_status)
            excerpt = re.sub(r"\s+", " ", hit.excerpt).strip()[:500]
            canon_lines.extend([
                f"{index}. [{hit.article.title}]({hit.article.canonical_url}) — {access}; "
                f"section `{hit.best_section}`; relevance {hit.score:.0%}.\n",
                f"   Grounded excerpt: {excerpt}\n",
            ])
        canon_lines.append("\n")
    context = build_archive_context(
        root=root, db_path=db_path,
        query="intelligence contractors, covert police programs, and international networks",
        canon_articles=5, voice_passages=6,
    )
    canon_lines.extend([
        "## Dry-run Codex prompt injection proof\n",
        "The same `build_archive_context` call used by `codex_articles.generate_prompt` produced both "
        "packets below without drafting an article.\n",
        f"- Canon packet heading present: {'# PUBLISHED WHITE RABBIT CANON' in context.canon_packet}\n",
        f"- Canon articles injected: {len(context.canon_memories)}\n",
        f"- Voice packet heading present: {'# WHITE RABBIT VOICE REFERENCES' in context.voice_packet}\n",
        f"- Voice passages injected: {len(context.voice_result.passages)}\n",
        "- Permanent source-authority and anti-AI requirements remain in the surrounding generated assignment.\n",
    ])
    canon_path = archive_root / "CANON_RETRIEVAL_SMOKE_TEST.md"
    canon_path.write_text("".join(canon_lines), encoding="utf-8")

    dry_run_path = archive_root / "DRY_RUN_CODEX_ASSIGNMENT.md"
    dry_run_path.write_text(
        "# Dry-run Codex investigative assignment — archive injection proof\n\n"
        "This is a prompt-assembly smoke test only. Do not draft or rewrite an article.\n\n"
        "## Test investigation\n\n"
        "Trace intelligence contractors, overseas police programs, and the personnel links "
        "that connect them. Preserve published canon, accepted-testimony provenance, and "
        "cumulative inference. Surface actual contradictions for author review.\n\n"
        "## Permanent controls\n\n"
        "Read `research_library/methodologies/SOURCE_AUTHORITY_AND_CANON.md`, "
        "`docs/WHITE_RABBIT_AUTHOR_VOICE.md`, and `docs/WHITE_RABBIT_ANTI_AI_STYLE.md`. "
        "Avoid repetitive antithesis, performed caution, lawyer voice, and defensive collapse.\n\n"
        + context.canon_packet + "\n\n" + context.voice_packet,
        encoding="utf-8",
    )

    voice_lines = [
        "# Voice Retrieval Smoke Test\n\n",
        "Query: `investigative intelligence contractor article`\n\n",
        "Only full-body authored prose is eligible. Markdown blockquotes, copied quotations, "
        "related-post cards, subscription/paywall UI, and partial-preview articles are excluded.\n\n",
    ]
    voice = retrieve_voice_references(db_path, "investigative intelligence contractor article", root=root, passage_limit=8)
    for index, passage in enumerate(voice.passages, 1):
        voice_lines.extend([
            f"## {index}. [{passage.article.title}]({passage.article.canonical_url})\n",
            f"- Location: {passage.section}, authored paragraph {passage.paragraph_number}\n",
            f"- Why stylistically relevant: {'; '.join(passage.traits)}\n",
            f"- Source body: `{Path(passage.article.local_dir) / 'article.md'}`\n",
            f"- Authored paragraph: {passage.text[:700]}\n\n",
        ])
    voice_lines.extend([
        "## Exclusion audit\n",
        f"- Full articles scanned: {voice.full_articles_scanned}\n",
        f"- Partial articles excluded: {voice.partial_articles_excluded}\n",
        f"- Quotation blocks excluded: {voice.quotation_blocks_excluded}\n",
        f"- UI/non-prose blocks excluded: {voice.ui_blocks_excluded}\n",
        f"- Authored prose blocks considered: {voice.prose_blocks_considered}\n",
    ])
    voice_path = archive_root / "VOICE_RETRIEVAL_SMOKE_TEST.md"
    voice_path.write_text("".join(voice_lines), encoding="utf-8")
    return {
        "inventory": str(inventory_path),
        "coverage_report": str(coverage_path),
        "canon_report": str(canon_path),
        "voice_report": str(voice_path),
        "dry_run_prompt": str(dry_run_path),
        "rows": len(rows),
        "years": {year: dict(counts) for year, counts in years.items()},
    }
