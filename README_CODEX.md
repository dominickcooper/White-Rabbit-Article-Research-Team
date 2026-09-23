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

See docs/CODEX_WORKFLOW.md and AGENTS.md for permanent authorities. This reconstruction
does not restore absent prior private articles.

## Standalone article versus series investigation

Use standalone for one self-contained investigation. Use a series for one investigation
whose installments share research, develop new findings and build on prior reader knowledge.
Standalone commands above are unchanged; existing projects are not migrated.

```powershell
python .\codex_article.py series new "SERIES TITLE"
python .\codex_article.py series add series-title "FIRST ARTICLE"
python .\codex_article.py series add series-title "SECOND ARTICLE" --finale
python .\codex_article.py series status series-title
python .\codex_article.py series prompt series-title part-01-first-article
python .\codex_article.py series validate series-title part-01-first-article
python .\codex_article.py series export series-title part-01-first-article
python .\codex_article.py series set-status series-title part-01-first-article complete
python .\codex_article.py series set-url series-title part-01-first-article "https://publication.example/p/first"
```

The series folder contains the manifest, brief, plan, timeline, entities, continuity,
shared_sources/, shared_research/master_dossier.md and articles/part-NN-slug/ projects.
Each part has the same brief/source/research/output layout and six final deliverables.
Put broadly useful sources in shared_sources and installment-specific sources under
the part; nothing needs copying between them.

Codex reads cumulative memory, adds new verified findings, preserves judgment revisions,
and updates reader-state continuity. Non-final endings open an evidence-led next question;
the finale synthesizes the investigation and responsibly examines modern relevance.
Published URLs become available in later prompts. Normalized paragraph duplication warns
at 40 words and fails at 300 matching words against one finalized part. Editorial audits
still judge recap necessity, novel value and evidentiary adequacy.

Use series set-finale <series> <last-part> to designate a finale, or add --clear to extend
the series before adding more parts. Full commands, directory structure, manifest/status
rules, validation and recovery notes: [Series workflow](docs/SERIES_WORKFLOW.md).
