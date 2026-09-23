# White Rabbit Codex Operating Kit

Root target:

`C:\Users\Cody\White-Rabbit-Article-Research-Team`

## One-time setup
Extract this kit into the repository root so `AGENTS.md`, `codex_article.py`, `docs/`, and `templates/` sit directly inside the project.

If your previous White Rabbit archive is not already under:

`research_library/previous_white_rabbit_articles/`

move or copy it there, or edit `white_rabbit_codex_config.json` to point at its actual location.

## Start an article
From PowerShell in the repository root:

```powershell
python .\codex_article.py new "COINTELPRO"
```

Optional explicit slug:

```powershell
python .\codex_article.py new "COINTELPRO" --slug cointelpro
```

This creates:

```text
article_projects/cointelpro/
├── ARTICLE_BRIEF.md
├── CODEX_PROMPT.md
├── sources/
├── research/
└── output/
```

Put author-provided PDFs, DOCX files, Markdown, transcripts, notes, images, and other research material into `sources/`.

Edit `ARTICLE_BRIEF.md` if you want to specify an angle or leads.

Then give Codex the contents of `CODEX_PROMPT.md` while Codex is opened on this repository.

## Check status

```powershell
python .\codex_article.py status cointelpro
```

Equivalent package commands are available without loading any provider integration:

```powershell
python -m white_rabbit article new "COINTELPRO"
python -m white_rabbit article status cointelpro
python -m white_rabbit article prompt cointelpro
python -m white_rabbit article validate cointelpro
python -m white_rabbit article export cointelpro
```

## Validate the finished project

```powershell
python .\codex_article.py validate cointelpro
```

The validator checks required outputs, article word count, image/subscribe/share markers, FAQ/related-reading sections, CSV phrase integrity, tracking parameters, and internal-link counts. It is a structural validator, not a substitute for the evidence audit Codex must perform.

## Export the finished article

After validation succeeds:

```powershell
python .\codex_article.py export cointelpro
```

This writes `output/article_substack.docx` and `output/article_substack.html` directly from the already-linked `output/article.md`. Existing inline Markdown links are preserved; no second linking pass is applied.

## Legacy provider commands

The former `python -m white_rabbit run`, `doctor`, and `archive rerank` commands remain available for compatibility and require Gemini configuration. They are optional and are not called by the Codex-first workflow.
