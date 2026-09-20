from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m white_rabbit.research_tools.get_pdf_pages TEXT_FILE PAGE_OR_RANGE...")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8", errors="replace")
    pages = {int(n): body for n, body in re.findall(r"===== PDF PAGE (\d+) =====\n(.*?)(?=\n===== PDF PAGE \d+ =====|\Z)", text, re.S)}
    wanted = []
    for spec in sys.argv[2:]:
        if "-" in spec:
            a, b = map(int, spec.split("-", 1))
            wanted.extend(range(a, b + 1))
        else:
            wanted.append(int(spec))
    for page in wanted:
        print(f"\n===== {path.name} PDF PAGE {page} =====\n{pages.get(page, '[MISSING PAGE]')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
