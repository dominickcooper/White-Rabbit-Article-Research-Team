from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("usage: python -m white_rabbit.research_tools.query_pdf_corpus CORPUS_DIR FILE_GLOB REGEX [MAX_PAGES]")
    corpus_dir = Path(sys.argv[1])
    file_glob = sys.argv[2]
    pattern = re.compile(sys.argv[3], re.IGNORECASE | re.MULTILINE)
    max_pages = int(sys.argv[4]) if len(sys.argv) > 4 else 50
    emitted = 0
    for path in sorted(corpus_dir.glob(file_glob)):
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks = re.split(r"\n===== PDF PAGE (\d+) =====\n", text)
        for index in range(1, len(chunks), 2):
            page_no = chunks[index]
            page_text = chunks[index + 1]
            match = pattern.search(page_text)
            if not match:
                continue
            start = max(0, match.start() - 500)
            end = min(len(page_text), match.end() + 1000)
            snippet = re.sub(r"\s+", " ", page_text[start:end]).strip()
            print(f"\n### {path.name} | PDF page {page_no}\n{snippet}")
            emitted += 1
            if emitted >= max_pages:
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
