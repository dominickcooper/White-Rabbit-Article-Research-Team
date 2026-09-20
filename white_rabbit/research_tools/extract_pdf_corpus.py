from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader


def safe_name(relative_path: Path) -> str:
    value = "__".join(relative_path.parts)
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:220]


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m white_rabbit.research_tools.extract_pdf_corpus SOURCE_ROOT OUTPUT_ROOT")
    source_root = Path(sys.argv[1]).resolve()
    output_root = Path(sys.argv[2]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for pdf_path in sorted(source_root.rglob("*.pdf")):
        relative = pdf_path.relative_to(source_root)
        record: dict[str, object] = {
            "path": str(relative).replace("\\", "/"),
            "bytes": pdf_path.stat().st_size,
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        }
        try:
            reader = PdfReader(str(pdf_path), strict=False)
            record["pages"] = len(reader.pages)
            record["metadata"] = {
                str(k): str(v) for k, v in (reader.metadata or {}).items()
            }
            parts: list[str] = []
            chars_by_page: list[int] = []
            for index, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception as exc:  # retain the corpus even when one page fails
                    page_text = f"[PAGE EXTRACTION ERROR: {type(exc).__name__}: {exc}]"
                chars_by_page.append(len(page_text.strip()))
                parts.append(f"\n===== PDF PAGE {index} =====\n{page_text}\n")
            text_value = "".join(parts)
            record["text_chars"] = len(text_value)
            record["nonempty_pages"] = sum(value >= 20 for value in chars_by_page)
            record["low_text_pages"] = [
                index for index, value in enumerate(chars_by_page, start=1) if value < 20
            ]
            output_path = output_root / f"{safe_name(relative)}.txt"
            output_path.write_text(text_value, encoding="utf-8", errors="replace")
            record["extracted_text"] = str(output_path)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)

    (output_root / "EXTRACTION_INDEX.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
