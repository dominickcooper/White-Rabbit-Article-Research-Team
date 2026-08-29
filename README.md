# White Rabbit Researcher — MVP

A research-first article pipeline for **The White Rabbit Report**.

This MVP proves one complete workflow:

**topic → Gemini research plan → Google-grounded web research + private source folder → evidence vault → outline → evidence-marked Markdown draft → AI source audit → exact phrase/source CSV → first-use hyperlink insertion → linked Markdown + DOCX + HTML + link report**

The existing `substack_source_linker.py` is preserved under `white_rabbit/publishing/` and reused for final hyperlinking/export.

## Why this MVP is intentionally single-article

Series architecture, persistent cross-project knowledge graphs, Ollama routing, embeddings/RAG, and a graphical UI are later phases. First we need to prove that one article can be produced with traceable evidence and clean publishing output.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your Gemini API key into:

```text
GEMINI_API_KEY=...
```

The default model is `gemini-3.7-flash` and can be changed in `.env`.

## Test API/config

```powershell
python -m white_rabbit doctor
```

## Run one test article

```powershell
python -m white_rabbit run "YOUR TOPIC HERE" --project test_article
```

Skip the automatic Substack sync when you only want to test writing:

```powershell
python -m white_rabbit run "YOUR TOPIC HERE" --project test_article --no-archive-sync
```

With private/local research material:

```powershell
python -m white_rabbit run "YOUR TOPIC HERE" --project test_article --sources "C:\Research\MySources"
```

Supported local inputs in this MVP:

- PDF
- DOCX
- Markdown
- TXT
- CSV
- JSON
- HTML

## Previous White Rabbit archive

Published articles live under `research_library/previous_white_rabbit_articles/` with a SQLite registry at `knowledge/white_rabbit.db`.

The hybrid search index (`knowledge/archive_search_index_v3.joblib`) is **local and rebuildable**. Do not commit it.

```powershell
python -m white_rabbit archive status
python -m white_rabbit archive reindex
python -m white_rabbit archive search "MKULTRA" --limit 8
```

## Project outputs

Each run creates:

```text
workspace/<project>/
├── evidence.sqlite3
├── research/
│   ├── research_plan.json
│   ├── web_research.json
│   ├── evidence_packet.md
│   └── source_audit.json
├── drafts/
│   ├── article_with_evidence_markers.md
│   └── article_unlinked.md
└── output/
    ├── article_linked.md
    ├── sources.csv
    ├── metadata.json
    ├── article_substack.docx
    ├── article_substack.html
    └── article_link_report.txt
```

## Important sourcing design

The system does **not** ask Gemini to research and immediately write. It stores research as source and evidence records first. The writer receives an evidence packet and is instructed to cite evidence IDs inline. Those IDs are later converted into exact article anchor phrases and public URLs.

Private sources remain in the evidence vault even when no public URL exists. They are not added to the hyperlink CSV unless they have a public URL.

## Privacy note

This Gemini MVP sends research excerpts and relevant local-source text to Gemini for analysis. If a private file must never leave the computer, do not place it in the source folder for this version. The later Ollama/private-RAG provider can keep those files local.

## Run tests

```powershell
pytest -q
```

## Next phases after the first successful article

1. Series planner: fixed count or Auto.
2. Persistent White Rabbit knowledge graph across investigations.
3. Ollama provider for private/local research and cheap bulk processing.
4. Hybrid escalation: Ollama first, Gemini for difficult questions/final synthesis.
5. Embeddings/vector retrieval for a large source library.
6. Sitemap ingestion and automatic internal White Rabbit links.
7. GUI/dashboard and research review controls.
