from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = HERE / "files"
TESTS = HERE / "tests"
DEPS = ["numpy>=1.26", "joblib>=1.4", "scikit-learn>=1.5"]


def run(cmd, **kwargs):
    print("  >", " ".join(map(str, cmd)))
    return subprocess.run(list(map(str, cmd)), cwd=ROOT, **kwargs)


def main() -> int:
    if not (ROOT / "white_rabbit").is_dir():
        print(f"ERROR: Expected White Rabbit project root at {ROOT}")
        return 2
    if not (ROOT / "knowledge" / "white_rabbit.db").exists():
        print("WARNING: knowledge/white_rabbit.db does not exist yet. The patch can install, but archive search needs a synced archive.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT / "upgrade_backups" / f"archive_retrieval_v3_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    replaced = [
        Path("white_rabbit/archive_retrieval.py"),
        Path("white_rabbit/cli.py"),
        Path("tests/test_archive_retrieval_v2.py"),
    ]
    for rel in replaced:
        src = ROOT / rel
        if src.exists():
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for src in FILES.rglob("*"):
        if src.is_file():
            rel = src.relative_to(FILES)
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for src in TESTS.glob("test_*.py"):
        dst = ROOT / "tests" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    req = ROOT / "requirements.txt"
    txt = req.read_text(encoding="utf-8") if req.exists() else ""
    with req.open("a", encoding="utf-8") as f:
        for dep in DEPS:
            name = dep.split(">", 1)[0].lower()
            if name not in txt.lower():
                if txt and not txt.endswith("\n"):
                    f.write("\n")
                f.write(dep + "\n")
                txt += "\n" + dep

    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)

    print(f"Backups: {backup}")
    print("Installing/checking retrieval dependencies...")
    result = run([py, "-m", "pip", "install", *DEPS])
    if result.returncode:
        return result.returncode

    env = os.environ.copy()
    env.update({
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    })

    print("Running tests...")
    result = run([py, "-m", "pytest", "-q", "tests"], env=env)
    if result.returncode:
        print("ERROR: tests failed. Existing files were backed up above.")
        return result.returncode

    db = ROOT / "knowledge" / "white_rabbit.db"
    if db.exists():
        print("Rebuilding Retrieval v3 archive index...")
        result = run([py, "-m", "white_rabbit", "archive", "reindex", "--force"], env=env)
        if result.returncode:
            return result.returncode

    print("\nArchive Retrieval v3 installed successfully.")
    print("Benchmark:")
    print('  python -m white_rabbit archive search "Flock Safety surveillance"')
    print("\nExpected behavior:")
    print("  - Flock Safety is treated as one primary entity.")
    print("  - standalone 'safety' no longer pulls vaccine/drug-safety articles.")
    print("  - conceptual surveillance/ALPR/camera-network connections may still surface.")
    print("  - internal White Rabbit links resolve to canonical archived titles/URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
