# Codex-first White Rabbit articles

This additive workflow uses Python for local project management, archive memory,
validation and export. Codex does the research/writing using the generated assignment.
The original Gemini pipeline, archive sync/search/reranking and local sources remain
available; see README.md. No LLM API key is required by these new commands.

Activate `.venv\Scripts\Activate.ps1` and install `pip install -r requirements.txt`.
Run from the repository (or invoke codex_article.py by its full path):

```powershell
python .\codex_article.py new "ARTICLE TOPIC"
python .\codex_article.py status article-topic
python .\codex_article.py prompt article-topic
# Give the prompt to Codex for research/writing, then:
python .\codex_article.py validate article-topic
python .\codex_article.py export article-topic
```

Edit the generated brief and put private sources in the project sources folder before
requesting research. New refuses existing destinations. Prompt refreshes only the
generated assignment. Status reports file presence, recursive source count, working
research files and deliverable readiness (not editorial approval).

```text
article_projects/<slug>/
  ARTICLE_BRIEF.md
  CODEX_PROMPT.md
  sources/
  research/
  output/
    research_dossier.md
    outline.md
    seo.md
    article.md
    sources.csv
    audit.md
    article_substack.docx
    article_substack.html
```

Validation checks deliverables, SEO fields, title, five FAQ headings, image/CTA markers,
related section, linked CSV anchors and clean HTTP(S) destinations. It reports total
links and unique/occurrence internal-link counts. PASS means mechanical validity, not
factual verification. Missing/irrelevant archive links require editorial explanation.
The exporter uses already-linked article.md; do not run first-use insertion again.
DOCX/HTML retain image and CTA placement notes for the Substack editor.

Configuration in white_rabbit_codex_config.json uses repository-relative paths.
internal_hosts supplements known archive registry URLs; use exact publication hostnames.
Change faq_count only with an intentional permanent standards change. Project contents
are ignored by Git by default to keep private research/generated prose out of commits.

See docs/CODEX_WORKFLOW.md and AGENTS.md for permanent authorities. Multi-part series
support is deferred. This reconstruction does not restore absent prior private articles.
