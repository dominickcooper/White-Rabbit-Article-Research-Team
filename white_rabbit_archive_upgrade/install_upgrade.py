from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ENV_DEFAULTS = {
    "WR_SUBSTACK_URL": "",
    "WR_WHITE_RABBIT_SITEMAP_URL": "",
    "WR_ARCHIVE_SYNC_BEFORE_RUN": "true",
    "WR_ARCHIVE_PLAN_CHUNKS": "10",
    "WR_ARCHIVE_WRITER_ARTICLES": "6",
    "WR_ARCHIVE_REQUEST_DELAY_MS": "120",
}

REPLACEMENT_PATHS = [
    Path("white_rabbit/config.py"),
    Path("white_rabbit/gemini_provider.py"),
    Path("white_rabbit/cli.py"),
    Path("white_rabbit/pipeline.py"),
    Path("requirements.txt"),
    Path("pytest.ini"),
]

REQUIRED_DIRS = [
    Path("research_library/previous_white_rabbit_articles/articles"),
    Path("research_library/previous_white_rabbit_articles/imports/substack_exports"),
    Path("research_library/previous_white_rabbit_articles/sync"),
    Path("research_library/projects"),
    Path("knowledge"),
]


def read_env(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").splitlines()


def env_value(lines: list[str], key: str) -> str:
    prefix = key.lower() + "="
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(prefix):
            return stripped.split("=", 1)[1].strip()
    return ""


def ensure_env_settings(path: Path) -> list[str]:
    lines = read_env(path)
    keys = {
        line.split("=", 1)[0].strip().lower()
        for line in lines
        if "=" in line and line.strip() and not line.lstrip().startswith("#")
    }

    if lines and lines[-1].strip():
        lines.append("")

    added = False
    for key, value in ENV_DEFAULTS.items():
        if key.lower() not in keys:
            lines.append(f"{key}={value}")
            added = True

    if added or not path.exists():
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return read_env(path)


def set_env_value(path: Path, key: str, value: str) -> None:
    lines = read_env(path)
    prefix = key.lower() + "="
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().lower().startswith(prefix):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def copy_upgrade_files(files_root: Path, project_root: Path) -> None:
    for src in files_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(files_root)
        dst = project_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def backup_existing(project_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = project_root / "upgrade_backups" / f"previous_articles_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    for rel in REPLACEMENT_PATHS:
        src = project_root / rel
        if src.exists() and src.is_file():
            dst = backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return backup_root


def run(cmd: list[str], cwd: Path) -> None:
    print("  > " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Previous White Rabbit Articles archive upgrade.")
    parser.add_argument("--substack-url", default=None, help="Publication root URL, e.g. https://name.substack.com")
    parser.add_argument("--skip-install", action="store_true", help="Skip pip install (testing/debug only).")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest (testing/debug only).")
    args = parser.parse_args()

    upgrade_root = Path(__file__).resolve().parent
    project_root = upgrade_root.parent
    files_root = upgrade_root / "files"

    print()
    print("WHITE RABBIT - PREVIOUS ARTICLES ARCHIVE UPGRADE")
    print(f"Project root: {project_root}")
    print()

    if not (project_root / "white_rabbit").is_dir():
        raise SystemExit(
            "ERROR: Extract white_rabbit_archive_upgrade directly into the White Rabbit Researcher project root."
        )
    if not files_root.is_dir():
        raise SystemExit(f"ERROR: Upgrade payload missing: {files_root}")

    backup_root = backup_existing(project_root)
    print(f"Backed up replaced files to: {backup_root}")

    copy_upgrade_files(files_root, project_root)
    print("Copied upgrade files.")

    for rel in REQUIRED_DIRS:
        (project_root / rel).mkdir(parents=True, exist_ok=True)
    print("Created archive/library directories.")

    env_path = project_root / ".env"
    env_lines = ensure_env_settings(env_path)

    current_substack = env_value(env_lines, "WR_SUBSTACK_URL")
    requested_substack = args.substack_url
    if requested_substack is None and not current_substack:
        print()
        try:
            requested_substack = input("Enter White Rabbit Substack URL (or press Enter to configure later): ").strip()
        except EOFError:
            requested_substack = ""

    if requested_substack:
        clean = requested_substack.strip().rstrip("/")
        set_env_value(env_path, "WR_SUBSTACK_URL", clean)
        print(f"Configured WR_SUBSTACK_URL={clean}")
    elif current_substack:
        print(f"Using existing WR_SUBSTACK_URL={current_substack}")
    else:
        print("WR_SUBSTACK_URL left blank; configure it in .env before archive sync.")

    python_exe = sys.executable
    print(f"Using Python: {python_exe}")

    if not args.skip_install:
        print()
        print("Installing/updating Python dependencies...")
        run([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], project_root)

    if not args.skip_tests:
        print()
        print("Running tests...")
        run([python_exe, "-m", "pytest", "-q", "tests"], project_root)

    print()
    print("Upgrade installed successfully.")
    print("Archive root: research_library\\previous_white_rabbit_articles")
    print("Knowledge DB: knowledge\\white_rabbit.db")
    print("Project sources: research_library\\projects\\<project_id>\\sources")
    print()
    print("Next commands:")
    print("  python -m white_rabbit archive sync")
    print("  python -m white_rabbit archive status")
    print("  python -m white_rabbit doctor")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
