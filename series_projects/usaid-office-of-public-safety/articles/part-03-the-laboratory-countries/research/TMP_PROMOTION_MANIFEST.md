# Part 3 temporary-work promotion manifest

Promoted during repository reconciliation on September 20, 2026. Original files remain
under `tmp/`; nothing was deleted.

## A. Reusable tooling

Six generic PDF/OCR utilities were copied from `tmp/pdfs/` to
`white_rabbit/research_tools/`:

- `extract_part03_corpus.py` → `extract_pdf_corpus.py`
- `extract_selected_part03.py` → `extract_selected_pdfs.py`
- `get_part03_pages.py` → `get_pdf_pages.py`
- `mark_ocr_sidecar_pages.py` → `mark_ocr_pages.py`
- `query_part03_corpus.py` → `query_pdf_corpus.py`
- `query_part03.py` → `query_pdf_text.py`

The Part 3-specific DOCX builder was copied to
`article_workspace/tools/build_part03_docx.py`.

## B. Non-reproducible research artifacts

None identified. The temporary corpus consists of derivatives of canonical source files
already retained in the Part 3 workspace.

## C. Source-derived text and indexes

All 65 `.txt` files and all three `.json` extraction indexes were copied, preserving
their relative structure, to:

- `research/source_derivatives/part03_corpus/`
- `research/source_derivatives/part03_targeted/`

These are derivatives, not canonical source documents, and therefore were not placed in
`sources/`.

## D. Rebuildable output

Left under `tmp/`:

- 32 page/render PNGs;
- four generated PDFs, including OCR intermediates and the rendered Part 3 PDF;
- all duplicate originals of the promoted scripts and derivative text/index files.

## E. Disposable cache/temp

No separate cache files were identified. The remaining `tmp/` tree is ignored as local
scratch space after the verified promotions above.
