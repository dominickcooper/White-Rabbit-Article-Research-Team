from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
from typing import Any, BinaryIO, Iterable
from uuid import uuid4
import zipfile

import pymupdf

from white_rabbit.local_sources import SUPPORTED as LOCAL_SUPPORTED, read_local_document
from .database import VaultDB
from .ingestion import evidence_archive_root, preserve_source, sha256_file


TEXT_TYPES = set(LOCAL_SUPPORTED) | {".pptx", ".xlsx", ".xlsm", ".tsv"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}
VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_TYPES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
SUPPORTED_TYPES = TEXT_TYPES | IMAGE_TYPES | VIDEO_TYPES | AUDIO_TYPES
REPORT_NAMES = (
    "inventory.csv", "manifest.json", "catalog.md", "folder_tree.txt",
    "conversion_status.csv", "extraction_errors.csv", "prioritized_review_queue.csv",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _config_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ArchiveImportConfig:
    max_members: int = 200_000
    max_total_bytes: int = 500 * 1024**3
    max_member_bytes: int = 100 * 1024**3
    max_expansion_ratio: float = 1000.0
    max_temp_bytes: int = 120 * 1024**3
    transcribe_media: bool = True
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    ocr_images: bool = False
    create_thumbnails: bool = True
    language: str | None = None

    def normalized(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InventoryItem:
    relative_path: str
    normalized_path: str
    filename: str
    extension: str
    media_type: str
    byte_size: int
    compressed_size: int | None = None
    crc32: str | None = None
    status: str = "pending"
    warning: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def classify_extension(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_TYPES:
        return "image"
    if suffix in VIDEO_TYPES:
        return "video"
    if suffix in AUDIO_TYPES:
        return "audio"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".pptx":
        return "presentation"
    if suffix in {".xlsx", ".xlsm"}:
        return "spreadsheet"
    if suffix in TEXT_TYPES:
        return "document"
    return "unsupported"


def normalize_member_path(name: str) -> tuple[str | None, str | None]:
    """Return a safe POSIX relative path and an optional rejection reason."""
    if "\x00" in name:
        return None, "NUL byte in archive member name"
    candidate = name.replace("\\", "/")
    pure = PurePosixPath(candidate)
    if pure.is_absolute() or candidate.startswith("/") or (pure.parts and ":" in pure.parts[0]):
        return None, "absolute archive member path"
    clean = [part for part in pure.parts if part not in {"", "."}]
    if not clean or any(part == ".." for part in clean):
        return None, "archive path traversal"
    return PurePosixPath(*clean).as_posix(), None


def _zip_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _check_limits(items: list[InventoryItem], config: ArchiveImportConfig) -> list[str]:
    warnings: list[str] = []
    if len(items) > config.max_members:
        raise ValueError(f"archive contains {len(items)} members; limit is {config.max_members}")
    total = sum(item.byte_size for item in items if item.status != "rejected")
    if total > config.max_total_bytes:
        raise ValueError(f"expanded size {total} exceeds configured limit {config.max_total_bytes}")
    if total > config.max_temp_bytes:
        warnings.append("expanded evidence exceeds the temporary-disk budget; processing remains one file at a time")
    return warnings


def preview_archive(source: Path | str, config: ArchiveImportConfig | None = None) -> dict[str, Any]:
    config = config or ArchiveImportConfig()
    source = Path(source).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    items: list[InventoryItem] = []
    seen: set[str] = set()
    warnings: list[str] = []
    if source.is_file():
        if source.suffix.lower() != ".zip":
            raise ValueError("archive source must be a ZIP file or a directory")
        source_kind = "zip"
        try:
            with zipfile.ZipFile(source) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    safe, reason = normalize_member_path(info.filename)
                    normalized = (safe or info.filename).casefold()
                    status, warning = "pending", None
                    if reason:
                        status, warning = "rejected", reason
                    elif _zip_is_symlink(info):
                        status, warning = "rejected", "symbolic links are not extracted"
                    elif normalized in seen:
                        status, warning = "rejected", "duplicate path collision after normalization"
                    elif info.file_size > config.max_member_bytes:
                        status, warning = "rejected", "member exceeds configured size limit"
                    elif info.compress_size and info.file_size / max(1, info.compress_size) > config.max_expansion_ratio:
                        status, warning = "rejected", "member expansion ratio exceeds ZIP-bomb threshold"
                    if safe:
                        seen.add(normalized)
                    media_type = classify_extension(safe or info.filename)
                    if status == "pending" and media_type == "unsupported":
                        status, warning = "quarantined", "unsupported format; original will be preserved without conversion"
                    items.append(InventoryItem(
                        safe or info.filename, normalized, Path(safe or info.filename).name,
                        Path(safe or info.filename).suffix.lower(), media_type, int(info.file_size),
                        int(info.compress_size), f"{info.CRC:08x}", status, warning,
                        {"archive_name": info.filename},
                    ))
        except zipfile.BadZipFile as exc:
            raise ValueError(f"malformed ZIP archive: {exc}") from exc
    elif source.is_dir():
        source_kind = "directory"
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                items.append(InventoryItem(relative, relative.casefold(), path.name, path.suffix.lower(),
                                           classify_extension(relative), 0, status="rejected",
                                           warning="symbolic links are not followed"))
                continue
            if not path.is_file():
                continue
            normalized = relative.casefold()
            status, warning = "pending", None
            size = path.stat().st_size
            if normalized in seen:
                status, warning = "rejected", "duplicate path collision after normalization"
            elif size > config.max_member_bytes:
                status, warning = "rejected", "file exceeds configured size limit"
            seen.add(normalized)
            media_type = classify_extension(relative)
            if status == "pending" and media_type == "unsupported":
                status, warning = "quarantined", "unsupported format; original will be preserved without conversion"
            items.append(InventoryItem(relative, normalized, path.name, path.suffix.lower(), media_type,
                                       size, status=status, warning=warning))
    else:
        raise ValueError("archive source must be a ZIP file or a directory")
    warnings.extend(_check_limits(items, config))
    accepted_bytes = sum(item.byte_size for item in items if item.status != "rejected")
    largest_member = max((item.byte_size for item in items if item.status != "rejected"), default=0)
    estimated_storage = accepted_bytes + largest_member
    free_bytes = shutil.disk_usage(source.parent).free
    if estimated_storage > free_bytes:
        warnings.append(
            f"estimated storage requirement {estimated_storage} exceeds available space {free_bytes}"
        )
    counts: dict[str, int] = {}
    for item in items:
        counts[item.media_type] = counts.get(item.media_type, 0) + 1
    return {
        "source_path": str(source), "source_kind": source_kind,
        "file_count": len(items), "total_bytes": sum(item.byte_size for item in items),
        "estimated_storage_bytes": estimated_storage, "available_storage_bytes": free_bytes,
        "counts": counts, "warnings": warnings,
        "integrity_check": "ZIP directory parsed; every member CRC is validated while streaming" if source_kind == "zip" else "directory entries are revalidated before copying",
        "items": [asdict(item) for item in items],
    }


def _source_hash(source: Path, kind: str) -> str:
    if kind == "zip":
        return sha256_file(source)
    digest = hashlib.sha256()
    for path in sorted(p for p in source.rglob("*") if p.is_file() and not p.is_symlink()):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(str(path.stat().st_size).encode())
        digest.update(str(path.stat().st_mtime_ns).encode())
    return digest.hexdigest()


def create_import_job(db: VaultDB, source: Path | str, *, investigation_name: str,
                      investigation_id: str | None = None, config: ArchiveImportConfig | None = None) -> tuple[str, dict[str, Any]]:
    config = config or ArchiveImportConfig()
    preview = preview_archive(source, config)
    source_path = Path(preview["source_path"])
    if investigation_id:
        if not db.conn.execute("SELECT 1 FROM investigations WHERE id=?", (investigation_id,)).fetchone():
            raise KeyError(f"unknown investigation: {investigation_id}")
    else:
        investigation_id = db.add_investigation(
            investigation_name.strip() or source_path.stem,
            "Evidence archive imported through the offline-first Intelligence Vault importer.",
        )
    job_id, now = _id("IMP"), _now()
    report_dir = db.path.resolve().parent / "intelligence_vault_imports" / job_id
    with db.transaction():
        db.conn.execute(
            """INSERT INTO archive_import_jobs(
                   id,source_path,source_kind,source_hash,investigation_id,status,config_json,total_files,
                   total_bytes,warning_count,report_directory,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, str(source_path), preview["source_kind"], _source_hash(source_path, preview["source_kind"]),
             investigation_id, "previewed", json.dumps(config.normalized()), preview["file_count"],
             preview["total_bytes"], len(preview["warnings"]), str(report_dir), now, now),
        )
        for raw in preview["items"]:
            item = InventoryItem(**raw)
            db.conn.execute(
                """INSERT INTO archive_import_files(
                       id,job_id,relative_path,normalized_path,filename,extension,media_type,byte_size,
                       compressed_size,crc32,status,warning,metadata_json,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_id("IMPF"), job_id, item.relative_path, item.normalized_path, item.filename,
                 item.extension, item.media_type, item.byte_size, item.compressed_size, item.crc32,
                 item.status, item.warning, json.dumps(item.metadata), now, now),
            )
    write_reports(db, job_id)
    return job_id, import_status(db, job_id, include_files=False)


def _job(db: VaultDB, job_id: str):
    row = db.conn.execute("SELECT * FROM archive_import_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise KeyError(f"unknown archive import job: {job_id}")
    return row


def set_job_action(db: VaultDB, job_id: str, action: str) -> dict[str, Any]:
    allowed = {"pause": "paused", "resume": "queued", "cancel": "cancelled", "retry": "queued"}
    if action not in allowed:
        raise ValueError("action must be pause, resume, cancel, or retry")
    _job(db, job_id)
    with db.transaction():
        if action == "retry":
            db.conn.execute(
                "UPDATE archive_import_files SET status='pending',processing_stage='inventory',error=NULL,updated_at=? WHERE job_id=? AND status='failed'",
                (_now(), job_id),
            )
        db.conn.execute("UPDATE archive_import_jobs SET status=?,error=NULL,updated_at=? WHERE id=?",
                        (allowed[action], _now(), job_id))
    return import_status(db, job_id)


def import_status(db: VaultDB, job_id: str, *, include_files: bool = True,
                  media_type: str | None = None, status: str | None = None,
                  folder: str | None = None) -> dict[str, Any]:
    row = dict(_job(db, job_id))
    row["config"] = json.loads(row.pop("config_json"))
    row["investigation"] = dict(db.conn.execute("SELECT * FROM investigations WHERE id=?", (row["investigation_id"],)).fetchone())
    if include_files:
        clauses, params = ["job_id=?"], [job_id]
        if media_type:
            clauses.append("media_type=?"); params.append(media_type)
        if status:
            clauses.append("status=?"); params.append(status)
        if folder:
            clauses.append("relative_path LIKE ?"); params.append(folder.rstrip("/") + "/%")
        row["files"] = [dict(item) for item in db.conn.execute(
            "SELECT * FROM archive_import_files WHERE " + " AND ".join(clauses) + " ORDER BY relative_path LIMIT 5000",
            params,
        )]
    row["reports"] = list(REPORT_NAMES)
    return row


def _materialize_member(job: dict[str, Any], relative_path: str, temporary: Path,
                        metadata: dict[str, Any] | None = None) -> None:
    source = Path(job["source_path"])
    if job["source_kind"] == "directory":
        candidate = (source / PurePosixPath(relative_path)).resolve()
        if not candidate.is_relative_to(source.resolve()) or candidate.is_symlink() or not candidate.is_file():
            raise ValueError("source file escaped the selected directory or changed type")
        shutil.copyfile(candidate, temporary)
        return
    with zipfile.ZipFile(source) as archive:
        info = archive.getinfo((metadata or {}).get("archive_name", relative_path))
        if _zip_is_symlink(info):
            raise ValueError("symbolic links are not extracted")
        with archive.open(info, "r") as input_stream, temporary.open("wb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def _pdf_text(path: Path) -> tuple[str, list[dict], list[str], str, str]:
    parts, locators, warnings = [], [], []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text")
            locator = {"page": index, "page_label": page.get_label() or str(index), "characters": len(text)}
            locators.append(locator)
            parts.append(f"\n\n[Page {index}]\n{text}")
            if not text.strip():
                warnings.append(f"page {index} has no extractable text and may require OCR")
    return "".join(parts).strip(), locators, warnings, "PyMuPDF", pymupdf.__doc__.split()[1] if pymupdf.__doc__ else "unknown"


def _pptx_text(path: Path) -> tuple[str, list[dict], list[str], str, str]:
    try:
        import pptx
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError("python-pptx is required for PPTX extraction") from exc
    presentation = Presentation(path)
    parts, locators = [], []
    for number, slide in enumerate(presentation.slides, start=1):
        values: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                values.append(shape.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    values.append(" | ".join(cell.text.strip() for cell in row.cells))
        try:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                values.append("Notes: " + notes)
        except (AttributeError, ValueError):
            pass
        text = "\n".join(values)
        parts.append(f"\n\n[Slide {number}]\n{text}")
        locators.append({"slide": number, "characters": len(text)})
    return "".join(parts).strip(), locators, [], "python-pptx", getattr(pptx, "__version__", "unknown")


def _spreadsheet_text(path: Path) -> tuple[str, list[dict], list[str], str, str]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for spreadsheet extraction") from exc
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts, locators = [], []
    for sheet in workbook.worksheets:
        rows = []
        for number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
            line = " | ".join("" if value is None else str(value) for value in values)
            if line.strip(" |"):
                rows.append(line)
                locators.append({"sheet": sheet.title, "row": number})
        parts.append(f"\n\n[Sheet: {sheet.title}]\n" + "\n".join(rows))
    workbook.close()
    return "".join(parts).strip(), locators, [], "openpyxl", getattr(openpyxl, "__version__", "unknown")


def _image_text(path: Path, config: ArchiveImportConfig, derivative_dir: Path) -> tuple[str, list[dict], list[str], str, str, list[dict]]:
    try:
        from PIL import ExifTags, Image, __version__ as pillow_version
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image metadata and thumbnails") from exc
    warnings, derivatives, text = [], [], ""
    with Image.open(path) as image:
        metadata = {"width": image.width, "height": image.height, "mode": image.mode, "format": image.format}
        exif = image.getexif()
        if exif:
            metadata["exif"] = {
                ExifTags.TAGS.get(key, str(key)): str(value)[:1000]
                for key, value in exif.items()
            }
        if config.create_thumbnails:
            thumb = image.copy(); thumb.thumbnail((640, 640))
            derivative_dir.mkdir(parents=True, exist_ok=True)
            target = derivative_dir / "thumbnail.jpg"
            if thumb.mode not in {"RGB", "L"}:
                thumb = thumb.convert("RGB")
            thumb.save(target, "JPEG", quality=82)
            derivatives.append({"type": "thumbnail", "path": target, "locator": metadata})
        if config.ocr_images:
            try:
                import pytesseract
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                tokens, confidences = [], []
                for token, confidence in zip(data.get("text", []), data.get("conf", [])):
                    if token.strip():
                        tokens.append(token.strip())
                        try: confidences.append(float(confidence))
                        except (TypeError, ValueError): pass
                text = " ".join(tokens)
                metadata["ocr_mean_confidence"] = sum(confidences) / len(confidences) if confidences else None
                warnings.append("OCR is machine-derived and must be reviewed against the original image")
            except (ImportError, OSError) as exc:
                warnings.append(f"OCR requested but unavailable: {exc}")
    return text, [metadata], warnings, "Pillow", pillow_version, derivatives


def _probe_media(path: Path) -> tuple[dict[str, Any], str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}, "FFmpeg/ffprobe is not installed"
    process = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if process.returncode:
        return {}, (process.stderr or "ffprobe failed")[:1000]
    return json.loads(process.stdout), ""


def _format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000)); hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000); secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _transcribe_media(path: Path, config: ArchiveImportConfig, derivative_dir: Path) -> tuple[str, list[dict], list[str], str, str, list[dict]]:
    probe, probe_warning = _probe_media(path)
    warnings = [probe_warning] if probe_warning else []
    streams = probe.get("streams", [])
    locators: list[dict] = [{"media_probe": probe}] if probe else []
    if probe and not any(stream.get("codec_type") == "audio" for stream in streams):
        warnings.append("media contains no audio stream; visual evidence requires manual examination")
        return "", locators, warnings, "ffprobe", "local", []
    if not config.transcribe_media:
        warnings.append("local transcription was disabled for this import")
        return "", locators, warnings, "ffprobe", "local", []
    try:
        from faster_whisper import WhisperModel
        import faster_whisper
    except ImportError:
        warnings.append("faster-whisper is not installed; original media was preserved for retry")
        return "", locators, warnings, "ffprobe", "local", []
    model = WhisperModel(config.whisper_model, device=config.whisper_device, compute_type="int8")
    segments, _ = model.transcribe(str(path), language=config.language, vad_filter=True)
    rows, srt = [], []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip(); rows.append(f"[{segment.start:.3f}-{segment.end:.3f}] {text}")
        locators.append({"start_seconds": segment.start, "end_seconds": segment.end, "text": text})
        srt.append(f"{index}\n{_format_timestamp(segment.start)} --> {_format_timestamp(segment.end)}\n{text}\n")
    derivative_dir.mkdir(parents=True, exist_ok=True)
    target = derivative_dir / "transcript.srt"; target.write_text("\n".join(srt), encoding="utf-8")
    return "\n".join(rows), locators, warnings, "faster-whisper", getattr(faster_whisper, "__version__", "unknown"), [{"type": "transcript_srt", "path": target, "locator": {}}]


def convert_file(path: Path, media_type: str, config: ArchiveImportConfig,
                 derivative_dir: Path) -> tuple[str, list[dict], list[str], str, str, list[dict]]:
    if media_type == "pdf":
        text, locators, warnings, tool, version = _pdf_text(path); return text, locators, warnings, tool, version, []
    if media_type == "presentation":
        text, locators, warnings, tool, version = _pptx_text(path); return text, locators, warnings, tool, version, []
    if media_type == "spreadsheet":
        text, locators, warnings, tool, version = _spreadsheet_text(path); return text, locators, warnings, tool, version, []
    if media_type == "image":
        return _image_text(path, config, derivative_dir)
    if media_type in {"audio", "video"}:
        return _transcribe_media(path, config, derivative_dir)
    if media_type == "unsupported":
        return "", [], ["unsupported format preserved without conversion"], "none", "n/a", []
    document = read_local_document(path)
    return document.text, [{"line_start": 1, "line_end": len(document.text.splitlines())}], [], "local_sources", "1", []


def _register_derivatives(db: VaultDB, file_id: str, derivatives: Iterable[dict], report_dir: Path) -> None:
    for item in derivatives:
        path = Path(item["path"])
        relative = path.relative_to(report_dir).as_posix()
        db.conn.execute(
            "INSERT OR IGNORE INTO archive_derivatives VALUES (?,?,?,?,?,?,?,?)",
            (_id("DER"), file_id, item["type"], relative, sha256_file(path),
             json.dumps(item.get("locator", {})), json.dumps(item.get("metadata", {})), _now()),
        )


def _attach_document_provenance(db: VaultDB, document_id: str, metadata: dict[str, Any],
                                job: dict[str, Any], relative_path: str) -> None:
    prior_row = db.conn.execute("SELECT metadata_json FROM documents WHERE id=?", (document_id,)).fetchone()
    prior = json.loads(prior_row[0] or "{}") if prior_row else {}
    members = list(prior.get("archive_members", []))
    member = {
        "source_archive": job["source_path"],
        "source_archive_hash": job["source_hash"],
        "original_relative_path": relative_path,
    }
    if member not in members:
        members.append(member)
    document_metadata = {**metadata, **prior} if prior else dict(metadata)
    document_metadata["archive_members"] = members
    db.conn.execute("UPDATE documents SET metadata_json=? WHERE id=?", (json.dumps(document_metadata), document_id))


def process_import_job(db: VaultDB, job_id: str) -> dict[str, Any]:
    job_row = _job(db, job_id); job = dict(job_row)
    if job["status"] in {"paused", "cancelled", "completed"}:
        return import_status(db, job_id)
    config = ArchiveImportConfig(**json.loads(job["config_json"]))
    report_dir = Path(job["report_directory"]); derivative_root = report_dir / "derivatives"
    report_dir.mkdir(parents=True, exist_ok=True)
    with db.transaction():
        db.conn.execute("UPDATE archive_import_jobs SET status='running',updated_at=? WHERE id=?", (_now(), job_id))
    rows = db.conn.execute(
        "SELECT * FROM archive_import_files WHERE job_id=? AND status IN ('pending','quarantined','failed') ORDER BY relative_path",
        (job_id,),
    ).fetchall()
    for row in rows:
        current = db.conn.execute("SELECT status FROM archive_import_jobs WHERE id=?", (job_id,)).fetchone()[0]
        if current in {"paused", "cancelled"}:
            break
        if row["status"] == "rejected":
            continue
        file_id = row["id"]
        suffix = row["extension"] or ".bin"
        fd, temp_name = tempfile.mkstemp(prefix="vault-import-", suffix=suffix, dir=db.path.parent)
        os.close(fd); temporary = Path(temp_name)
        try:
            with db.transaction():
                db.conn.execute("UPDATE archive_import_files SET status='processing',processing_stage='materialize',updated_at=? WHERE id=?", (_now(), file_id))
            _materialize_member(job, row["relative_path"], temporary, json.loads(row["metadata_json"] or "{}"))
            if temporary.stat().st_size != row["byte_size"]:
                raise RuntimeError("materialized byte size does not match inventory")
            digest = sha256_file(temporary)
            archived_path = preserve_source(temporary, evidence_archive_root(db), digest)
            config_hash = _config_hash(config.normalized())
            derivative_dir = derivative_root / file_id
            with db.transaction():
                db.conn.execute("UPDATE archive_import_files SET sha256=?,processing_stage='convert',updated_at=? WHERE id=?", (digest, _now(), file_id))
            cached = db.conn.execute(
                """SELECT * FROM archive_import_files
                   WHERE id<>? AND sha256=? AND conversion_config_hash=?
                     AND status IN ('completed','completed_with_warning')
                     AND document_id IS NOT NULL AND revision_id IS NOT NULL
                   ORDER BY updated_at DESC LIMIT 1""",
                (file_id, digest, config_hash),
            ).fetchone()
            if cached:
                prior_metadata = json.loads(cached["metadata_json"] or "{}")
                warnings = list(prior_metadata.get("warnings", []))
                warnings.append("reused cached conversion for identical content and configuration")
                metadata = {
                    **prior_metadata,
                    "source_archive": job["source_path"],
                    "source_archive_hash": job["source_hash"],
                    "original_relative_path": row["relative_path"],
                    "original_filename": row["filename"],
                    "content_hash": digest,
                    "content_classification": "author_supplied",
                    "processing_status": "completed_with_warning",
                    "warnings": warnings,
                }
                warning = "; ".join(filter(None, [row["warning"], *warnings]))
                with db.transaction():
                    _attach_document_provenance(db, cached["document_id"], metadata, job, row["relative_path"])
                    db.attach_document_investigation(cached["document_id"], job["investigation_id"], f"Imported from {row['relative_path']}")
                    db.conn.execute(
                        """UPDATE archive_import_files SET status='completed_with_warning',processing_stage='complete',
                           warning=?,error=NULL,document_id=?,revision_id=?,extracted_characters=?,locator_count=?,
                           conversion_tool=?,conversion_version=?,conversion_config_hash=?,metadata_json=?,updated_at=? WHERE id=?""",
                        (warning, cached["document_id"], cached["revision_id"], cached["extracted_characters"],
                         cached["locator_count"], cached["conversion_tool"], cached["conversion_version"],
                         config_hash, json.dumps(metadata), _now(), file_id),
                    )
                continue
            text, locators, warnings, tool, version, derivatives = convert_file(temporary, row["media_type"], config, derivative_dir)
            source_locator = f"{job['source_path']}::{row['relative_path']}" if job["source_kind"] == "zip" else str((Path(job["source_path"]) / PurePosixPath(row["relative_path"])).resolve())
            document_id, revision_id, _ = db.add_document_revision(
                title=Path(row["relative_path"]).stem.replace("_", " "), file_hash=digest,
                extracted_text=text, byte_size=row["byte_size"], original_file=source_locator,
                source_classification="author_supplied", authority_level=2, archived_path=archived_path,
            )
            metadata = {
                "source_archive": job["source_path"], "source_archive_hash": job["source_hash"],
                "original_relative_path": row["relative_path"], "original_filename": row["filename"],
                "content_hash": digest, "content_classification": "author_supplied",
                "processing_status": "completed_with_warning" if warnings else "completed",
                "media_type": row["media_type"], "locators": locators,
                "conversion": {"tool": tool, "version": version, "config_hash": _config_hash(config.normalized())},
                "warnings": warnings, "derivative_of": None,
            }
            with db.transaction():
                _attach_document_provenance(db, document_id, metadata, job, row["relative_path"])
                db.attach_document_investigation(document_id, job["investigation_id"], f"Imported from {row['relative_path']}")
                _register_derivatives(db, file_id, derivatives, report_dir)
                warning = "; ".join(filter(None, [row["warning"], *warnings])) or None
                db.conn.execute(
                    """UPDATE archive_import_files SET status=?,processing_stage='complete',warning=?,error=NULL,
                       document_id=?,revision_id=?,extracted_characters=?,locator_count=?,conversion_tool=?,
                       conversion_version=?,conversion_config_hash=?,metadata_json=?,updated_at=? WHERE id=?""",
                    ("completed_with_warning" if warning else "completed", warning, document_id, revision_id,
                     len(text), len(locators), tool, version, config_hash, json.dumps(metadata), _now(), file_id),
                )
        except Exception as exc:
            with db.transaction():
                db.conn.execute("UPDATE archive_import_files SET status='failed',processing_stage='failed',error=?,updated_at=? WHERE id=?",
                                (str(exc)[:2000], _now(), file_id))
        finally:
            temporary.unlink(missing_ok=True)
        _refresh_counts(db, job_id)
        write_reports(db, job_id)
    _refresh_counts(db, job_id)
    remaining = db.conn.execute("SELECT COUNT(*) FROM archive_import_files WHERE job_id=? AND status IN ('pending','processing','quarantined')", (job_id,)).fetchone()[0]
    current = db.conn.execute("SELECT status FROM archive_import_jobs WHERE id=?", (job_id,)).fetchone()[0]
    if current not in {"paused", "cancelled"}:
        final = "completed" if not remaining else "interrupted"
        with db.transaction():
            db.conn.execute("UPDATE archive_import_jobs SET status=?,updated_at=?,completed_at=? WHERE id=?", (final, _now(), _now() if final == "completed" else None, job_id))
    write_reports(db, job_id)
    return import_status(db, job_id)


def _refresh_counts(db: VaultDB, job_id: str) -> None:
    counts = db.conn.execute(
        """SELECT SUM(CASE WHEN status IN ('completed','completed_with_warning') THEN 1 ELSE 0 END),
                  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN warning IS NOT NULL THEN 1 ELSE 0 END)
           FROM archive_import_files WHERE job_id=?""", (job_id,),
    ).fetchone()
    with db.transaction():
        db.conn.execute("UPDATE archive_import_jobs SET completed_files=?,failed_files=?,warning_count=?,updated_at=? WHERE id=?",
                        (counts[0] or 0, counts[1] or 0, counts[2] or 0, _now(), job_id))


def write_reports(db: VaultDB, job_id: str) -> Path:
    job = dict(_job(db, job_id)); report_dir = Path(job["report_directory"]); report_dir.mkdir(parents=True, exist_ok=True)
    files = [dict(row) for row in db.conn.execute("SELECT * FROM archive_import_files WHERE job_id=? ORDER BY relative_path", (job_id,))]
    inventory_fields = ["relative_path", "filename", "extension", "media_type", "byte_size", "compressed_size", "crc32", "status", "warning"]
    with (report_dir / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=inventory_fields); writer.writeheader()
        for item in files: writer.writerow({key: item.get(key) for key in inventory_fields})
    conversion_fields = ["relative_path", "sha256", "status", "processing_stage", "document_id", "revision_id", "extracted_characters", "locator_count", "conversion_tool", "conversion_version", "warning", "error"]
    with (report_dir / "conversion_status.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=conversion_fields); writer.writeheader()
        for item in files: writer.writerow({key: item.get(key) for key in conversion_fields})
    errors = [item for item in files if item.get("error")]
    with (report_dir / "extraction_errors.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["relative_path", "stage", "error"]); writer.writeheader()
        for item in errors: writer.writerow({"relative_path": item["relative_path"], "stage": item["processing_stage"], "error": item["error"]})
    priority_names = {"roj.sobib.mra/SOBIB2008DIRECTORY.pdf", "Legacy_Program_Forensic_Audit.pdf", "Legacy_Program_Forensic_Audit.pptx", "Forensic_Audit_of_Disclosure_Channels (2).pdf", "Forensic_Audit_of_Disclosure_Channels (1).pptx", "Organize_Safety_Tactical_Briefing.pdf", "The_Architecture_of_Project_MONARCH__Engineering_the_Dissociati.mp4", "assetreclamationcloseout.mp4", "disclosure.mp4"}
    queue = sorted(files, key=lambda item: (0 if item["relative_path"] in priority_names or item["filename"] in priority_names else 1, 0 if item["media_type"] in {"pdf", "presentation"} else 1, item["relative_path"].casefold()))
    with (report_dir / "prioritized_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["priority", "relative_path", "media_type", "status", "document_id", "warning"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for index, item in enumerate(queue, start=1): writer.writerow({"priority": index, **{key: item.get(key) for key in fields[1:]}})
    tree: list[str] = []
    emitted: set[tuple[str, ...]] = set()
    for item in files:
        parts = PurePosixPath(item["relative_path"]).parts
        for depth in range(1, len(parts)):
            key = parts[:depth]
            if key not in emitted:
                tree.append("  " * (depth - 1) + parts[depth - 1] + "/")
                emitted.add(key)
        tree.append("  " * (len(parts) - 1) + parts[-1])
    (report_dir / "folder_tree.txt").write_text("\n".join(tree), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in files: counts[item["media_type"]] = counts.get(item["media_type"], 0) + 1
    manifest = {"schema_version": 1, "job": {key: job[key] for key in job if key != "config_json"}, "config": json.loads(job["config_json"]), "counts": counts, "reports": list(REPORT_NAMES), "files": [{key: item.get(key) for key in ("relative_path", "byte_size", "sha256", "status", "document_id", "revision_id")} for item in files]}
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    catalog = [f"# Evidence Archive Catalog — {job_id}", "", f"Source: `{job['source_path']}`", f"Status: **{job['status']}**", f"Files: **{len(files):,}**", "", "## Format counts", ""]
    catalog += [f"- {kind}: {count:,}" for kind, count in sorted(counts.items())]
    catalog += ["", "## Files", ""]
    catalog += [
        f"- `{item['relative_path']}` — {item['media_type']}; {item['status']}; "
        f"SHA-256 `{item.get('sha256') or 'pending'}`"
        for item in files
    ]
    catalog += ["", "## Review boundary", "", "Extracted text, OCR, and transcripts are derivatives of the original evidence and are not independent corroborating sources. Allegations and named-person wrongdoing require human review before acceptance."]
    (report_dir / "catalog.md").write_text("\n".join(catalog), encoding="utf-8")
    return report_dir


def report_path(db: VaultDB, job_id: str, name: str) -> Path:
    if name not in REPORT_NAMES:
        raise ValueError("unknown import report")
    root = Path(_job(db, job_id)["report_directory"]).resolve()
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise FileNotFoundError(name)
    return candidate
