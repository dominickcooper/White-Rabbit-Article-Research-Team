from __future__ import annotations

import hashlib
from pathlib import Path
import socket
import stat
import sys
import zipfile

import pytest

from white_rabbit.intelligence_vault.archive_importer import (
    ArchiveImportConfig,
    create_import_job,
    import_status,
    normalize_member_path,
    preview_archive,
    process_import_job,
    report_path,
    set_job_action,
)
from white_rabbit.intelligence_vault.database import VaultDB


def make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return path


def test_preview_rejects_unsafe_members_collisions_symlinks_and_bomb_ratio(tmp_path: Path):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../escape.txt", b"escape")
        archive.writestr("/absolute.txt", b"absolute")
        archive.writestr("Folder/Note.txt", b"first")
        archive.writestr("folder/note.txt", b"collision")
        link = zipfile.ZipInfo("link.txt")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, b"target")
        archive.writestr("huge.txt", b"0" * 50_000)
    preview = preview_archive(archive_path, ArchiveImportConfig(max_expansion_ratio=5))
    by_path = {item["relative_path"]: item for item in preview["items"]}
    assert by_path["../escape.txt"]["status"] == "rejected"
    assert by_path["/absolute.txt"]["status"] == "rejected"
    assert by_path["folder/note.txt"]["status"] == "rejected"
    assert by_path["link.txt"]["status"] == "rejected"
    assert by_path["huge.txt"]["status"] == "rejected"
    assert normalize_member_path(r"safe\nested\file.txt")[0] == "safe/nested/file.txt"
    with VaultDB(tmp_path / "unsafe.db") as db:
        job_id, status = create_import_job(db, archive_path, investigation_name="Unsafe Inventory",
                                           config=ArchiveImportConfig(max_expansion_ratio=5))
        assert status["total_files"] == 6
        assert import_status(db, job_id)["completed_files"] == 0


def test_mixed_import_preserves_bytes_provenance_dedup_and_reports(tmp_path: Path):
    shared = b"Alpha source text with a searchable Monarch phrase.\n"
    archive_path = make_zip(tmp_path / "evidence.zip", {
        "briefs/alpha.txt": shared,
        "copies/alpha-copy.txt": shared,
        "binary/opaque.xyz": b"\x00\x01original",
    })
    db_path = tmp_path / "vault.db"
    with VaultDB(db_path) as db:
        job_id, initial = create_import_job(db, archive_path, investigation_name="Synthetic Archive")
        assert initial["status"] == "previewed"
        result = process_import_job(db, job_id)
        assert result["status"] == "completed"
        assert result["completed_files"] == 3
        assert db.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert db.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
        assert db.conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0] == 0
        text_file = next(item for item in result["files"] if item["relative_path"] == "briefs/alpha.txt")
        document = db.get_document(text_file["document_id"])
        metadata = document["metadata"]
        assert metadata["original_relative_path"] == "briefs/alpha.txt"
        assert metadata["source_archive"] == str(archive_path.resolve())
        assert metadata["locators"] == [{"line_start": 1, "line_end": 1}]
        archived = db.archived_file(document["revisions"][0]["archived_path"])
        assert archived.read_bytes() == shared
        assert archived.name == hashlib.sha256(shared).hexdigest()
        assert db.search("searchable Monarch phrase")["documents"]
        assert db.conn.execute("SELECT COUNT(*) FROM document_investigations").fetchone()[0] == 2
        for name in result["reports"]:
            assert report_path(db, job_id, name).is_file()
        assert "opaque.xyz" in report_path(db, job_id, "catalog.md").read_text(encoding="utf-8")
        assert process_import_job(db, job_id)["completed_files"] == 3
        second_job, _ = create_import_job(db, archive_path, investigation_name="Synthetic Archive")
        second = process_import_job(db, second_job)
        assert second["completed_files"] == 3
        assert db.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert all("reused cached conversion" in (item["warning"] or "") for item in second["files"])


def test_pause_resume_retry_and_corrupt_pdf_preserves_original(tmp_path: Path):
    archive_path = make_zip(tmp_path / "resume.zip", {
        "one.txt": b"one",
        "bad.pdf": b"not a pdf",
    })
    with VaultDB(tmp_path / "vault.db") as db:
        job_id, _ = create_import_job(db, archive_path, investigation_name="Resume Test")
        paused = set_job_action(db, job_id, "pause")
        assert paused["status"] == "paused"
        assert process_import_job(db, job_id)["completed_files"] == 0
        set_job_action(db, job_id, "resume")
        result = process_import_job(db, job_id)
        assert result["completed_files"] == 1 and result["failed_files"] == 1
        failed = next(item for item in result["files"] if item["status"] == "failed")
        digest = hashlib.sha256(b"not a pdf").hexdigest()
        assert failed["sha256"] == digest
        assert (tmp_path / "intelligence_vault_evidence" / "sha256" / digest[:2] / digest).read_bytes() == b"not a pdf"
        retried = set_job_action(db, job_id, "retry")
        assert next(item for item in retried["files"] if item["relative_path"] == "bad.pdf")["status"] == "pending"


def test_limits_and_report_path_validation(tmp_path: Path):
    archive_path = make_zip(tmp_path / "small.zip", {"a.txt": b"a", "b.txt": b"b"})
    with pytest.raises(ValueError, match="members"):
        preview_archive(archive_path, ArchiveImportConfig(max_members=1))
    with VaultDB(tmp_path / "vault.db") as db:
        job_id, _ = create_import_job(db, archive_path, investigation_name="Limits")
        assert import_status(db, job_id, folder="nope")["files"] == []
        with pytest.raises(ValueError, match="unknown import report"):
            report_path(db, job_id, "../vault.db")


def test_streaming_media_fallback_and_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archive_path = make_zip(tmp_path / "media.zip", {
        "large.txt": b"streamed" * 200_000,
        "clip.mp4": b"synthetic-corrupt-video",
    })
    monkeypatch.setattr(zipfile.ZipFile, "read", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("whole-member ZipFile.read must not be used")
    ))
    monkeypatch.setattr("white_rabbit.intelligence_vault.archive_importer.shutil.which", lambda _: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("archive import attempted a network connection")
    ))
    with VaultDB(tmp_path / "vault.db") as db:
        job_id, _ = create_import_job(db, archive_path, investigation_name="Offline Media")
        result = process_import_job(db, job_id)
        assert result["completed_files"] == 2
        media = next(item for item in result["files"] if item["media_type"] == "video")
        assert media["status"] == "completed_with_warning"
        assert "ffprobe" in media["warning"] and "faster-whisper" in media["warning"]


def test_malformed_zip_is_rejected(tmp_path: Path):
    malformed = tmp_path / "bad.zip"
    malformed.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="malformed ZIP"):
        preview_archive(malformed)
