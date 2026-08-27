from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = HERE / "files"


def main() -> int:
    if not (ROOT / "white_rabbit").is_dir():
        print(f"ERROR: Expected White Rabbit project root at {ROOT}")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT / "upgrade_backups" / f"archive_search_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    for rel in [Path("white_rabbit/cli.py"), Path("white_rabbit/archive_retrieval.py")]:
        src = ROOT / rel
        if src.exists():
            dest = backup / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    for src in FILES.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(FILES)
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    test_src = HERE / "tests" / "test_archive_search_cli.py"
    test_dest = ROOT / "tests" / "test_archive_search_cli.py"
    shutil.copy2(test_src, test_dest)

    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)

    print(f"Backups: {backup}")
    print("Running tests...")
    result = subprocess.run([str(python), "-m", "pytest", "-q", "tests"], cwd=ROOT)
    if result.returncode:
        print("ERROR: Tests failed. Restore from the backup above if needed.")
        return result.returncode

    print("\nArchive search patch installed successfully.")
    print('Try: python -m white_rabbit archive search "Flock Safety surveillance"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
