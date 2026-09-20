from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pypdf import PdfReader


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m white_rabbit.research_tools.extract_selected_pdfs OUTPUT_DIR PDF...")
    output_dir = Path(sys.argv[1]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for raw in sys.argv[2:]:
        path = Path(raw).resolve()
        record = {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            reader = PdfReader(path, strict=False)
            record["pages"] = len(reader.pages)
            record["metadata"] = {str(k): str(v) for k, v in (reader.metadata or {}).items()}
            text_parts = []
            counts = []
            errors = []
            for page_number, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text() or ""
                except Exception as exc:
                    text = ""
                    errors.append({"page": page_number, "error": f"{type(exc).__name__}: {exc}"})
                counts.append(len(text.strip()))
                text_parts.append(f"\n===== PDF PAGE {page_number} =====\n{text}\n")
            output = output_dir / f"{path.stem}.txt"
            output.write_text("".join(text_parts), encoding="utf-8", errors="replace")
            record.update({
                "text_chars": sum(counts),
                "nonempty_pages": sum(v >= 20 for v in counts),
                "low_text_pages": [i for i, v in enumerate(counts, 1) if v < 20],
                "extraction_errors": errors,
                "output": str(output),
            })
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
    index = output_dir / "SELECTED_EXTRACTION_INDEX.json"
    index.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
