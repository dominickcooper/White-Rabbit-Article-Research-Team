from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m white_rabbit.research_tools.mark_ocr_pages INPUT.txt OUTPUT.txt")
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    pages = source.read_text(encoding="utf-8", errors="replace").split("\f")
    marked = []
    for number, page in enumerate(pages, start=1):
        marked.append(f"\n===== PDF PAGE {number} =====\n{page.strip()}\n")
    output.write_text("\n".join(marked), encoding="utf-8")
    print(f"wrote {len(pages)} page blocks to {output}")


if __name__ == "__main__":
    main()
