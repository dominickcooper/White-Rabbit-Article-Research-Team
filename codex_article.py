#!/usr/bin/env python3
"""White Rabbit Codex article project scaffolder and structural validator.

No third-party dependencies required.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "white_rabbit_codex_config.json"
DEFAULT_CONFIG = {
    "article_projects_dir": "article_projects",
    "archive_dir": "research_library/previous_white_rabbit_articles",
    "shared_sources_dir": "research_library/shared",
    "publication_base_url": "https://thewhiterabbitreport.substack.com",
    "default_word_min": 2000,
    "default_word_max": 3500,
    "internal_link_min": 3,
    "internal_link_max": 6,
    "image_marker_min": 5,
    "image_marker_max": 10,
    "subscribe_marker_target": 3,
}

REQUIRED_OUTPUTS = [
    "research_dossier.md",
    "outline.md",
    "seo.md",
    "article.md",
    "sources.csv",
    "audit.md",
]

TRACKING_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid"
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception as exc:
            print(f"WARNING: Could not read {CONFIG_PATH.name}: {exc}", file=sys.stderr)
    return cfg


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "article"


def project_dir(slug: str, cfg: dict) -> Path:
    if slug != slugify(slug) or not slug:
        raise ValueError("Project slug must contain only lowercase letters, numbers, and hyphens")
    return ROOT / cfg["article_projects_dir"] / slug


def configured_path(value: str) -> Path:
    """Resolve a configured repository path while allowing an explicit absolute path."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def archive_dir(cfg: dict) -> Path:
    return configured_path(str(cfg["archive_dir"]))


def archive_article_count(cfg: dict) -> int:
    archive = archive_dir(cfg)
    articles = archive / "articles" if (archive / "articles").is_dir() else archive
    return sum(1 for path in articles.rglob("article.md") if path.is_file()) if articles.exists() else 0


def render_template(path: Path, replacements: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def codex_prompt(topic: str, slug: str) -> str:
    return f"""# CODEX ARTICLE ASSIGNMENT\n\nYou are working in the repository `C:\\Users\\Cody\\White-Rabbit-Article-Research-Team`.\n\nProduce a complete White Rabbit Report investigation on:\n\n**{topic}**\n\nProject slug: `{slug}`\n\nBefore doing substantive work, read the root `AGENTS.md` and every standards document it requires. Then read:\n\n`article_projects/{slug}/ARTICLE_BRIEF.md`\n\nTreat the repository instructions and project brief as the authority for this assignment.\n\nWork autonomously through the entire workflow. Do not stop after source review, research notes, an outline, or a draft. Research the supplied files, research additional material online when network access is available, use the previous White Rabbit archive as institutional memory and for internal-link discovery, build the dossier and outline, create the SEO package, write the complete article, add image/subscribe/share markers, hyperlink claims to appropriate sources, create the source CSV, add the five-question FAQ and related-articles section, perform the adversarial audit, apply the audit corrections, and validate the final project.\n\nRequired project source folder:\n\n`article_projects/{slug}/sources/`\n\nRequired final output folder:\n\n`article_projects/{slug}/output/`\n\nRequired final files:\n\n- `research_dossier.md`\n- `outline.md`\n- `seo.md`\n- `article.md`\n- `sources.csv`\n- `audit.md`\n\nImportant execution rules:\n\n1. Inspect all relevant files in the project's `sources/` directory before broad web research.\n2. Search the previous White Rabbit archive for meaningful prior connections and internal links. Reopen original sources for important claims when possible.\n3. Research beyond the supplied sources. Prefer government records, congressional material, court filings, patents, contracts, FOIA/declassified records, SEC filings, scientific literature, official company/university documents, archival reporting, and other primary material. Wikipedia may be used for discovery, but consequential claims should normally be traced to stronger sources.\n4. Follow documented rabbit holes involving intelligence agencies, defense contractors, investors, banks, foundations, universities, surveillance firms, Big Tech, military programs, patents, subcontractors, shared personnel, family/business relationships, and historical covert programs when the evidence justifies following them.\n5. Clearly separate documented fact, strong inference, plausible connection, and speculation. Do not force the article toward a predetermined conclusion.\n6. Include the strongest credible conventional explanation and explain both what it accounts for and what remains unresolved.\n7. The final article must be publication-ready Markdown and must follow the White Rabbit house voice and formatting rules.\n8. Insert useful visual notes as `[IMAGE: description | ALT: alt text]`.\n9. Insert `[[SUBSCRIBE]]` and `[[SHARE]]` markers where editorially useful, between paragraphs/sections.\n10. The final Markdown must contain inline hyperlinks adhering to the repository sourcing rules, including genuinely relevant links to previous White Rabbit articles.\n11. Include exactly five useful FAQs and then `## YOU MAY BE INTERESTED IN THESE ARTICLES` with 3–6 relevant archived White Rabbit links when available.\n12. Do not invent facts, quotes, URLs, record identifiers, affiliations, or inaccessible source contents. Log research gaps instead.\n13. Before finishing, run `python codex_article.py validate {slug}` and fix meaningful validation failures.\n14. Do not merely report audit problems. Apply the corrections to the final files.\n\nWhen complete, report only a concise production summary: final title, word count, source counts, internal-link count, image/subscribe/share counts, unresolved research gaps, validator result, and paths to the six final deliverables.\n"""


def cmd_new(args: argparse.Namespace) -> int:
    cfg = load_config()
    slug = args.slug or slugify(args.topic)
    pdir = project_dir(slug, cfg)
    (pdir / "sources").mkdir(parents=True, exist_ok=True)
    (pdir / "research").mkdir(parents=True, exist_ok=True)
    (pdir / "output").mkdir(parents=True, exist_ok=True)

    brief = pdir / "ARTICLE_BRIEF.md"
    if not brief.exists() or args.force:
        brief.write_text(
            render_template(
                ROOT / "templates" / "ARTICLE_BRIEF_TEMPLATE.md",
                {"TOPIC": args.topic, "PROJECT_SLUG": slug},
            ),
            encoding="utf-8",
        )

    prompt_path = pdir / "CODEX_PROMPT.md"
    if not prompt_path.exists() or args.force:
        prompt_path.write_text(codex_prompt(args.topic, slug), encoding="utf-8")

    archive = archive_dir(cfg)
    print(f"Created/verified project: {pdir}")
    print(f"Topic: {args.topic}")
    print(f"Slug: {slug}")
    print(f"Sources: {pdir / 'sources'}")
    print(f"Codex prompt: {prompt_path}")
    if archive.exists():
        print(f"White Rabbit archive: FOUND ({archive}; {archive_article_count(cfg)} article(s))")
    else:
        print(f"White Rabbit archive: NOT FOUND at configured path ({archive})")
        print("  Copy/move the archive there or edit white_rabbit_codex_config.json.")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    cfg = load_config()
    pdir = project_dir(args.slug, cfg)
    prompt_path = pdir / "CODEX_PROMPT.md"
    if not prompt_path.exists():
        print(f"Prompt not found: {prompt_path}", file=sys.stderr)
        return 1
    print(prompt_path.read_text(encoding="utf-8"))
    return 0


def word_count(markdown: str) -> int:
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r" \1 ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return len(re.findall(r"\b[\w’'-]+\b", text))


def markdown_links(markdown: str) -> list[tuple[str, str]]:
    return re.findall(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", markdown)


def malformed_markdown_links(markdown: str) -> list[str]:
    problems: list[str] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if re.search(r"\[[^\]]+\]\(https?://[^\s)]*\s+[^)]*\)", line):
            problems.append(f"line {line_number}: URL contains whitespace")
        if re.search(r"\[[^\]]+\]\(https?://[^)]*$", line):
            problems.append(f"line {line_number}: unclosed Markdown link")
    return problems


def has_tracking(url: str) -> bool:
    try:
        query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    except Exception:
        return False
    return any(k.lower() in TRACKING_KEYS or k.lower().startswith("utm_") for k in query)


def validation_report(slug: str, cfg: dict) -> tuple[list[str], list[str], dict]:
    pdir = project_dir(slug, cfg)
    out = pdir / "output"
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict = {}

    if not pdir.exists():
        errors.append(f"Project directory does not exist: {pdir}")
        return errors, warnings, metrics

    for name in REQUIRED_OUTPUTS:
        if not (out / name).exists():
            errors.append(f"Missing required output: output/{name}")

    article_path = out / "article.md"
    csv_path = out / "sources.csv"
    if not article_path.exists():
        return errors, warnings, metrics

    article = article_path.read_text(encoding="utf-8", errors="replace")
    wc = word_count(article)
    images = len(re.findall(r"\[IMAGE:\s*.*?\|\s*ALT:\s*.*?\]", article, flags=re.I | re.S))
    subscribe = article.count("[[SUBSCRIBE]]")
    share = article.count("[[SHARE]]")
    links = markdown_links(article)
    base = cfg["publication_base_url"].rstrip("/")
    internal = [(a, u) for a, u in links if u.startswith(base)]
    external = [(a, u) for a, u in links if not u.startswith(base)]
    unique_internal = {u.rstrip("/") for _, u in internal}

    metrics.update({
        "word_count": wc,
        "image_markers": images,
        "subscribe_markers": subscribe,
        "share_markers": share,
        "markdown_links": len(links),
        "internal_link_occurrences": len(internal),
        "unique_internal_white_rabbit_articles": len(unique_internal),
        "external_links": len(external),
    })

    if wc < int(cfg["default_word_min"]):
        warnings.append(f"Article is short for the default target: {wc} words")
    if images < int(cfg["image_marker_min"]):
        warnings.append(f"Only {images} image markers; usual target starts at {cfg['image_marker_min']}")
    if subscribe == 0:
        errors.append("No [[SUBSCRIBE]] markers found")
    if share == 0:
        errors.append("No [[SHARE]] markers found")
    if "## YOU MAY BE INTERESTED IN THESE ARTICLES" not in article.upper():
        errors.append("Missing 'YOU MAY BE INTERESTED IN THESE ARTICLES' section")

    faq_heading = re.search(r"^##\s+.*FAQ", article, flags=re.I | re.M)
    if not faq_heading:
        errors.append("No FAQ H2 section detected")
    else:
        tail = article[faq_heading.start():]
        related_idx = tail.upper().find("## YOU MAY BE INTERESTED IN THESE ARTICLES")
        faq_block = tail if related_idx < 0 else tail[:related_idx]
        faq_questions = len(re.findall(r"^###\s+.+\?\s*$", faq_block, flags=re.M))
        metrics["faq_questions"] = faq_questions
        if faq_questions != 5:
            errors.append(f"Detected {faq_questions} FAQ H3 questions; expected exactly 5")

    if len(unique_internal) < int(cfg["internal_link_min"]):
        warnings.append(
            f"Only {len(unique_internal)} unique internal White Rabbit articles; usual target starts at "
            f"{cfg['internal_link_min']}"
        )

    for problem in malformed_markdown_links(article):
        errors.append(f"Malformed Markdown link ({problem})")

    for anchor, url in links:
        if has_tracking(url):
            errors.append(f"Tracking parameters remain in link: {url}")

    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            expected = ["source_number", "phrase", "link"]
            if rows or f is not None:
                # DictReader fieldnames is available after context manager too via rows only indirectly,
                # so reopen cheaply for a precise header check.
                with csv_path.open("r", encoding="utf-8-sig", newline="") as f2:
                    reader2 = csv.DictReader(f2)
                    fieldnames = reader2.fieldnames or []
                if fieldnames != expected:
                    errors.append(f"sources.csv header must be exactly: {','.join(expected)}")
            missing_phrases = []
            link_mismatches = []
            tracking_csv = []
            for row in rows:
                phrase = (row.get("phrase") or "").strip()
                url = (row.get("link") or "").strip()
                if phrase and phrase not in article:
                    missing_phrases.append(phrase)
                elif phrase and url and f"]({url})" not in article:
                    link_mismatches.append((phrase, url))
                if url and has_tracking(url):
                    tracking_csv.append(url)
            metrics["source_csv_rows"] = len(rows)
            if missing_phrases:
                errors.append(f"{len(missing_phrases)} CSV phrase(s) do not appear exactly in article.md")
                for phrase in missing_phrases[:8]:
                    warnings.append(f"CSV phrase missing from article: {phrase}")
            if tracking_csv:
                errors.append(f"{len(tracking_csv)} source CSV URL(s) still contain tracking parameters")
            if link_mismatches:
                errors.append(
                    f"{len(link_mismatches)} CSV source relationship(s) do not match an inline Markdown link"
                )
        except Exception as exc:
            errors.append(f"Could not validate sources.csv: {exc}")

    return errors, warnings, metrics


def cmd_export(args: argparse.Namespace) -> int:
    """Export the already-linked publication Markdown without reinserting links."""
    cfg = load_config()
    out = project_dir(args.slug, cfg) / "output"
    article_path = out / "article.md"
    if not article_path.exists():
        print(f"Article not found: {article_path}", file=sys.stderr)
        return 1
    try:
        from white_rabbit.publishing.substack_source_linker import (
            markdown_to_docx,
            markdown_to_html,
            wrap_html,
        )
        article = article_path.read_text(encoding="utf-8-sig")
        docx_path = out / "article_substack.docx"
        html_path = out / "article_substack.html"
        markdown_to_docx(article, docx_path)
        body = markdown_to_html(article)
        title_match = re.search(r"^#\s+(.+)$", article, flags=re.M)
        title = title_match.group(1).strip() if title_match else args.slug.replace("-", " ").title()
        html_path.write_text(wrap_html(body, title), encoding="utf-8")
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    print(f"DOCX: {docx_path}")
    print(f"HTML: {html_path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    pdir = project_dir(args.slug, cfg)
    if not pdir.exists():
        print(f"Project not found: {pdir}", file=sys.stderr)
        return 1
    print(f"Project: {pdir}")
    for rel in ["ARTICLE_BRIEF.md", "CODEX_PROMPT.md", "sources", "research", "output"]:
        path = pdir / rel
        if path.is_dir():
            count = sum(1 for x in path.rglob("*") if x.is_file())
            print(f"  {rel}/: {count} file(s)")
        else:
            print(f"  {rel}: {'present' if path.exists() else 'missing'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = load_config()
    errors, warnings, metrics = validation_report(args.slug, cfg)
    print(f"VALIDATION: {args.slug}")
    print("=" * 72)
    for key, value in metrics.items():
        print(f"{key}: {value}")
    if warnings:
        print("\nWARNINGS")
        for item in warnings:
            print(f"- {item}")
    if errors:
        print("\nFAILURES")
        for item in errors:
            print(f"- {item}")
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="White Rabbit Codex article helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create an article project workspace")
    p_new.add_argument("topic", help="Article topic")
    p_new.add_argument("--slug", help="Optional explicit project slug")
    p_new.add_argument("--force", action="store_true", help="Overwrite generated brief/prompt")
    p_new.set_defaults(func=cmd_new)

    p_prompt = sub.add_parser("prompt", help="Print a project's Codex prompt")
    p_prompt.add_argument("slug")
    p_prompt.set_defaults(func=cmd_prompt)

    p_status = sub.add_parser("status", help="Show project workspace status")
    p_status.add_argument("slug")
    p_status.set_defaults(func=cmd_status)

    p_validate = sub.add_parser("validate", help="Validate finished article deliverables")
    p_validate.add_argument("slug")
    p_validate.set_defaults(func=cmd_validate)

    p_export = sub.add_parser("export", help="Export final article.md to DOCX and HTML")
    p_export.add_argument("slug")
    p_export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
