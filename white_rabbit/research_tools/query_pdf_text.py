from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m white_rabbit.research_tools.query_pdf_text TEXT_FILE REGEX [MAX_RESULTS]")
    path = Path(sys.argv[1])
    pattern = re.compile(sys.argv[2], re.I)
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    text = path.read_text(encoding="utf-8", errors="replace")
    pages = re.findall(
        r"===== PDF PAGE (\d+) =====\n(.*?)(?=\n===== PDF PAGE \d+ =====|\Z)",
        text,
        re.S,
    )
    results = 0
    for page_number, body in pages:
        compact = re.sub(r"\s+", " ", body)
        for match in pattern.finditer(compact):
            start = max(0, match.start() - 260)
            end = min(len(compact), match.end() + 520)
            print(f"PDF PAGE {page_number}: {compact[start:end]}")
            results += 1
            if results >= limit:
                return


if __name__ == "__main__":
    main()
