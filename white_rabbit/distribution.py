"""Offline, evidence-grounded distribution packages for Codex series projects.

This module never calls a model, network service, or publishing API.  It derives a
review package from canonical series files and writes only below ``distribution/``.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit, urlunsplit

from . import codex_articles, codex_series

CAMPAIGN_ID = "USAID-CIA-2026"
CAMPAIGN_SLUG = "usaid_cia_2026"
BASE_URL = "https://thewhiterabbitreport.substack.com/"
CLASSIFICATIONS = {"DOCUMENTED_FACT", "STRONG_INFERENCE", "PLAUSIBLE_CONNECTION", "SPECULATION"}
STATUSES = ("GENERATED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "REVISION_REQUESTED", "READY_TO_PUBLISH", "PUBLISHED")
TRANSITIONS = {
    "GENERATED": {"NEEDS_REVIEW"}, "NEEDS_REVIEW": {"APPROVED", "REJECTED", "REVISION_REQUESTED"},
    "REVISION_REQUESTED": {"NEEDS_REVIEW", "REJECTED"}, "APPROVED": {"READY_TO_PUBLISH", "REVISION_REQUESTED"},
    "READY_TO_PUBLISH": {"PUBLISHED", "REVISION_REQUESTED"}, "REJECTED": set(), "PUBLISHED": set(),
}
ANALYTICS_FIELDS = ["content_id", "campaign_id", "article_id", "platform", "format", "hook_family", "duration_bucket", "presentation_style", "cta_family", "publish_time", "views", "reach", "impressions", "watch_time", "average_watch_time", "completion_rate", "likes", "comments", "shares", "saves", "profile_visits", "link_clicks", "free_signups", "paid_signups", "referrals", "revenue", "data_collected_at"]
EVIDENCE_FIELDS = ["claim_id", "content_id", "claim_text", "claim_classification", "source_number", "source_phrase", "source_url", "article_id", "article_section", "source_file", "source_strength", "review_required", "notes"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def article_id(part: int) -> str:
    if not 1 <= part <= 99:
        raise ValueError("Part number must be between 1 and 99.")
    return f"USAID-CIA-P{part:02d}"


def content_id(part: int, platform: str, format_name: str, number: int) -> str:
    clean = lambda value: re.sub(r"[^A-Z0-9]+", "", value.upper())
    return f"WRR-USAIDCIA-P{part:02d}-{clean(platform)}-{clean(format_name)}-{number:03d}"


def utm_url(base_url: str, source: str, medium: str, cid: str) -> str:
    parsed = urlsplit(base_url)
    query = urlencode({"utm_source": source, "utm_medium": medium, "utm_campaign": CAMPAIGN_SLUG, "utm_content": cid})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def transition_status(current: str, target: str) -> None:
    if current not in TRANSITIONS or target not in TRANSITIONS[current]:
        raise ValueError(f"Invalid approval transition: {current} -> {target}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Missing source file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def discover(root: Path, series_slug: str) -> tuple[Path, dict]:
    series, manifest = codex_series.load(root, series_slug)
    if len(manifest["parts"]) != 7 or [p["number"] for p in manifest["parts"]] != list(range(1, 8)):
        raise ValueError("USAID campaign requires exactly seven sequential parts.")
    return series, manifest


def campaign_manifest(series: Path, source: dict) -> dict:
    parts = []
    for part in source["parts"]:
        project = series / "articles" / part["slug"]
        seo = (project / "output/seo.md").read_text(encoding="utf-8-sig") if (project / "output/seo.md").is_file() else ""
        field = lambda name: (re.search(rf"(?ims)^## {re.escape(name)}\s*\n(.+?)(?=^## |\Z)", seo).group(1).strip() if re.search(rf"(?ims)^## {re.escape(name)}\s*\n(.+?)(?=^## |\Z)", seo) else None)
        parts.append({"article_id": article_id(part["number"]), "part_number": part["number"], "title": part["title"],
            "subtitle": field("Reader-Facing Description / Sizzle"), "slug": part["slug"], "status": part["status"],
            "publication_url": part["published_url"], "free_paid_status": "UNKNOWN", "primary_keyword": field("Primary Keyword"),
            "canonical_path": str(project.relative_to(series)).replace("\\", "/"), "source_files": [str((project / "output/sources.csv").relative_to(series)).replace("\\", "/")],
            "image_assets": [str(p.relative_to(series)).replace("\\", "/") for p in project.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
            "information_scope": "CURRENT_PART", "next_article_id": article_id(part["number"] + 1) if part["number"] < 7 else None})
    return {"schema_version": 1, "campaign_id": CAMPAIGN_ID, "campaign_title": "USAID & THE CIA", "campaign_slug": CAMPAIGN_SLUG,
        "number_of_parts": 7, "source_series_slug": source["slug"], "article_order": [p["article_id"] for p in parts], "articles": parts,
        "spoiler_policy": {"allowed": ["CURRENT_PART", "PRIOR_PARTS", "TEASER_SAFE"], "blocked": ["FUTURE_PARTS"]},
        "publication_mode": "HUMAN_REVIEW_ONLY", "generated_at": now()}


def spoiler_allowed(asset_part: int, fact_part: int, teaser_safe: bool = False) -> bool:
    return fact_part <= asset_part or teaser_safe


def _claims(series: Path) -> list[dict]:
    from .distribution_creative import extract_claim_library
    project = series / "articles/part-01-usaid-article"
    return extract_claim_library(series, _read_csv(project / "output/sources.csv"))
    # Legacy implementation retained below for schema-history readability.
    project = series / "articles/part-01-usaid-article"
    sources = _read_csv(project / "output/sources.csv")
    article = (project / "output/article.md").read_text(encoding="utf-8-sig")
    specs = [
        ("CLM-USAIDCIA-P01-001", "NSAM 177 assigned AID operating and funding responsibility for foreign police programs while excluding covert aspects.", 1, "THE ORDER WITH THE EXCEPTION"),
        ("CLM-USAIDCIA-P01-002", "Kennedy treated police assistance as part of the response to Communist indirect aggression in NSAM 132.", 2, "THE PROGRAM THAT DID NOT FIT DEVELOPMENT"),
        ("CLM-USAIDCIA-P01-003", "NSAM 162 discussed police, paramilitary and military resources in a wider internal-defense frame.", 3, "THE ARCHITECTURE TAKES SHAPE"),
        ("CLM-USAIDCIA-P01-004", "A July 1962 interagency committee recommended an AID-led structure with roles retained by State and Defense.", 4, "THE ARCHITECTURE TAKES SHAPE"),
    ]
    result = []
    for claim_id, text, number, section in specs:
        src = next((r for r in sources if r["source_number"] == str(number)), None)
        if not src or src["phrase"] not in article:
            raise ValueError(f"Unsupported claim {claim_id}: source anchor absent")
        result.append({"claim_id": claim_id, "claim_text": text, "claim_classification": "DOCUMENTED_FACT", "source_number": number,
            "source_phrase": src["phrase"], "source_url": src["link"], "article_id": article_id(1), "article_section": section,
            "source_file": str((project / "output/sources.csv").relative_to(series)).replace("\\", "/"), "source_strength": "PRIMARY_OR_OFFICIAL_RECORD",
            "review_required": "YES", "notes": "Wording is a bounded paraphrase; reviewer must compare against article context."})
    return result


def _asset_specs() -> list[tuple[str, str, str, str]]:
    specs = []
    def add(platform, fmt, count, family):
        for _ in range(count): specs.append((platform, fmt, family, "social" if platform not in {"TT", "YT", "RD", "SUB"} else {"TT":"video", "YT":"video", "RD":"community", "SUB":"note"}[platform]))
    add("TT", "SHORT", 3, "DOCUMENT"); add("TT", "MEDIUM", 2, "OFFICIAL_RECORD"); add("TT", "LONGSHORT", 1, "TIMELINE")
    add("FB", "PHOTO", 3, "DOCUMENT"); add("FB", "REEL", 2, "CONTRADICTION"); add("FB", "LONG", 1, "TIMELINE")
    add("IG", "REEL", 3, "QUESTION"); add("IG", "CAROUSEL", 1, "FOLLOW_THE_PAPER_TRAIL"); add("IG", "IMAGE", 1, "DOCUMENT")
    add("X", "POST", 5, "OFFICIAL_RECORD"); add("X", "THREAD", 1, "TIMELINE"); add("X", "IMAGE", 3, "DOCUMENT")
    add("SUB", "NOTE", 4, "CONNECTION"); add("YT", "SHORT", 3, "CONTRADICTION"); add("RD", "POST", 1, "ORDINARY_EXPLANATION_VS_RECORD")
    add("REF", "CTA", 3, "QUESTION"); add("PAID", "CTA", 3, "FOLLOW_THE_PAPER_TRAIL"); add("SERIES", "TEASER", 3, "MYSTERY")
    return specs


def build_part(series: Path, source_manifest: dict, *, dry_run: bool = False, refresh_existing: bool = False) -> dict:
    from .distribution_creative import build_part_v2
    return build_part_v2(series, source_manifest, dry_run=dry_run, refresh_existing=refresh_existing)
    # Sprint 1 deterministic placeholder implementation retained below.
    out = series / "distribution/part-01"; campaign_dir = series / "distribution/campaign"
    claims = _claims(series); generated = now(); counters = {}; assets = []
    platform_names = {"TT":"tiktok", "FB":"facebook", "IG":"instagram", "X":"x", "SUB":"substack", "YT":"youtube", "RD":"reddit", "REF":"referral", "PAID":"paid", "SERIES":"series"}
    for platform, fmt, family, medium in _asset_specs():
        key=(platform,fmt); counters[key]=counters.get(key,0)+1; cid=content_id(1,platform,fmt,counters[key])
        claim = claims[(len(assets)) % len(claims)]
        assets.append({"content_id": cid, "experiment_id": "EXP-HOOK-001" if platform in {"TT","YT"} else "", "campaign_id": CAMPAIGN_ID,
            "article_id": article_id(1), "platform": platform_names[platform], "format": fmt, "hook_family": family,
            "duration_bucket": fmt if fmt in {"SHORT","MEDIUM","LONGSHORT"} else "", "presentation_style": "FACE_PLUS_DOCUMENTS" if platform in {"TT","YT"} else "DOCUMENT_LED_VOICEOVER",
            "cta_family": "READ_PART_1", "status": "NEEDS_REVIEW", "generated_at": generated, "approved_at": "", "published_at": "",
            "source_asset": "articles/part-01-usaid-article/output/article.md", "target_url": source_manifest["parts"][0]["published_url"] or BASE_URL,
            "supported_claim_ids": [claim["claim_id"]], "copy": f"Follow the documents: {claim['claim_text']} What does the record show—and what does it not prove?",
            "hook": claim["claim_text"], "experiment_notes": "Heuristic test metadata; not scientifically validated."})
    if dry_run:
        return {"would_write": str(out), "asset_count": len(assets), "claim_count": len(claims)}
    out.mkdir(parents=True, exist_ok=True); campaign_dir.mkdir(parents=True, exist_ok=True)
    evidence=[]; utms=[]
    for asset in assets:
        source=asset["platform"] if asset["platform"] != "series" else "substack"; medium={"substack":"note","tiktok":"video","youtube":"video","reddit":"community"}.get(source,"social")
        final=utm_url(asset["target_url"],source,medium,asset["content_id"])
        utms.append({"content_id":asset["content_id"],"article_id":article_id(1),"platform":asset["platform"],"base_url":asset["target_url"],"utm_source":source,"utm_medium":medium,"utm_campaign":CAMPAIGN_SLUG,"utm_content":asset["content_id"],"final_url":final})
        for claim_id in asset["supported_claim_ids"]:
            row=next(c for c in claims if c["claim_id"]==claim_id).copy(); row["content_id"]=asset["content_id"]; evidence.append(row)
    registry_fields=["content_id","experiment_id","campaign_id","article_id","platform","format","hook_family","duration_bucket","presentation_style","cta_family","status","generated_at","approved_at","published_at","source_asset","target_url"]
    _write_csv(campaign_dir/"content_registry.csv",registry_fields,assets)
    _write_csv(out/"utm_links.csv",["content_id","article_id","platform","base_url","utm_source","utm_medium","utm_campaign","utm_content","final_url"],utms)
    _write_csv(out/"evidence_manifest.csv",EVIDENCE_FIELDS,evidence)
    _write_csv(out/"approval_queue.csv",["content_id","status","reviewer","decision","notes","timestamp","revision_history"],[{"content_id":a["content_id"],"status":"NEEDS_REVIEW","reviewer":"","decision":"","notes":"","timestamp":"","revision_history":"[]"} for a in assets])
    _write_csv(campaign_dir/"analytics_import_template.csv",ANALYTICS_FIELDS,[])
    _write_csv(campaign_dir/"experiment_manifest.csv",["experiment_id","dimension","variants","status","notes"],[{"experiment_id":"EXP-HOOK-001","dimension":"hook_family","variants":"DOCUMENT|OFFICIAL_RECORD|CONTRADICTION|QUESTION","status":"PLANNED","notes":"Internal heuristic test; no performance claims."}])
    hooks=[{"hook_id":f"HOOK-P01-{i:03d}","hook_family":a["hook_family"],"hook_text":a["hook"],"supported_claim_ids":"|".join(a["supported_claim_ids"]),"curiosity_score":4,"specificity_score":5,"evidence_strength_score":5,"spoiler_risk":"LOW","notes":"Scores are editorial heuristics only."} for i,a in enumerate(assets[:13],1)]
    _write_csv(out/"hooks.csv",list(hooks[0]),hooks); _write_csv(campaign_dir/"series_hooks.csv",list(hooks[0]),hooks)
    groups={"video_scripts.md":{"tiktok"},"facebook.md":{"facebook"},"instagram.md":{"instagram"},"x_posts.md":{"x"},"substack_notes.md":{"substack"},"youtube_shorts.md":{"youtube"},"reddit.md":{"reddit"},"referral_ctas.md":{"referral"},"paid_ctas.md":{"paid"},"part_02_teasers.md":{"series"}}
    for filename, platforms in groups.items():
        body=[f"# {filename.removesuffix('.md').replace('_',' ').title()}","","> DRAFT — human review required. Nothing here has been published.",""]
        for a in [x for x in assets if x["platform"] in platforms]:
            body += [f"## {a['content_id']}","",f"- Hook family: {a['hook_family']}",f"- Evidence: {', '.join(a['supported_claim_ids'])}",f"- Presentation: {a['presentation_style']}","",a["copy"],"",f"CTA: Read Part 1 and follow the paper trail.","", "Visual: show the authentic cited document or a clearly labeled graphic; never present generated imagery as archival evidence.",""]
        (out/filename).write_text("\n".join(body),encoding="utf-8")
    # Separate thread artifact required by the package contract.
    thread=next(a for a in assets if a["platform"]=="x" and a["format"]=="THREAD")
    (out/"x_thread.md").write_text(f"# X thread — {thread['content_id']}\n\nDRAFT — NEEDS_REVIEW\n\n1/ {thread['copy']}\n\n2/ The record draws a boundary between overt administration and covert aspects. It does not prove institutional identity.\n\nEvidence: {', '.join(thread['supported_claim_ids'])}\n",encoding="utf-8")
    dist={"schema_version":1,"campaign_id":CAMPAIGN_ID,"article_id":article_id(1),"prompt_version":"distribution-v1-offline-template","model_used":None,"generation_timestamp":generated,"source_inputs":["SERIES_MANIFEST.json","SERIES_CONTINUITY.md","articles/part-01-usaid-article/output/article.md","articles/part-01-usaid-article/output/sources.csv"],"asset_count":len(assets),"claim_count":len(claims),"publishing_performed":False,"assets":assets}
    (out/"distribution_manifest.json").write_text(json.dumps(dist,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"output":str(out),"asset_count":len(assets),"claim_count":len(claims)}


def build_campaign(root: Path, slug: str, *, dry_run=False) -> dict:
    series, source = discover(root, slug); manifest=campaign_manifest(series,source)
    if dry_run: return {"would_write":str(series/"distribution/campaign"),"articles":len(manifest["articles"])}
    out=series/"distribution/campaign"; out.mkdir(parents=True,exist_ok=True)
    (out/"campaign_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=["# USAID & THE CIA — Distribution Campaign","",f"Campaign ID: `{CAMPAIGN_ID}`","","> Review-only campaign. No publishing integration exists.",""]
    lines += [f"{p['part_number']}. `{p['article_id']}` — {p['title']} (`{p['slug']}`)" for p in manifest["articles"]]
    (out/"campaign_manifest.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"output":str(out),"articles":7}


def validate_analytics(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig",newline="") as h: reader=csv.DictReader(h); rows=list(reader)
    errors=[]
    if reader.fieldnames != ANALYTICS_FIELDS: errors.append("Analytics header does not match schema.")
    numeric=set(ANALYTICS_FIELDS[ANALYTICS_FIELDS.index("views"):ANALYTICS_FIELDS.index("data_collected_at")])
    for line,row in enumerate(rows,2):
        for field in numeric:
            if row.get(field) and not re.fullmatch(r"\d+(?:\.\d+)?",row[field]): errors.append(f"Row {line}: {field} must be nonnegative numeric.")
    return errors


def validate_package(root: Path, slug: str, part: int=1) -> dict:
    from .distribution_creative import validate_package_v2
    return validate_package_v2(root, slug, part)
    # Sprint 1 validator retained below for schema-history readability.
    series, _=discover(root,slug); out=series/f"distribution/part-{part:02d}"; errors=[]
    required=["distribution_manifest.json","evidence_manifest.csv","approval_queue.csv","utm_links.csv"]
    for name in required:
        if not (out/name).is_file(): errors.append(f"Missing {name}")
    if not errors:
        manifest=json.loads((out/"distribution_manifest.json").read_text(encoding="utf-8")); ids=[a["content_id"] for a in manifest["assets"]]
        if len(ids)!=len(set(ids)): errors.append("Duplicate content IDs.")
        evidence=_read_csv(out/"evidence_manifest.csv"); covered={r["content_id"] for r in evidence}
        for row in evidence:
            if row["claim_classification"] not in CLASSIFICATIONS: errors.append(f"Invalid classification: {row['claim_id']}")
            if not row["source_phrase"] or not row["source_file"]: errors.append(f"Unsupported claim: {row['claim_id']}")
        if set(ids)-covered: errors.append("Assets without evidence rows: "+", ".join(sorted(set(ids)-covered)))
        if any(a["status"]=="PUBLISHED" for a in manifest["assets"]): errors.append("Generated assets may not be PUBLISHED.")
    analytics=series/"distribution/campaign/analytics_import_template.csv"
    if analytics.is_file(): errors.extend(validate_analytics(analytics))
    else: errors.append("Missing analytics template.")
    return {"campaign_id":CAMPAIGN_ID,"part":part,"errors":errors,"result":"FAIL" if errors else "PASS"}


def main(argv: list[str]|None=None, *, root: Path|None=None) -> int:
    parser=argparse.ArgumentParser(description="White Rabbit Distribution Engine (review only; never publishes)")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("build-campaign","build-part","validate"):
        p=sub.add_parser(name); p.add_argument("series_slug"); p.add_argument("--part",type=int,default=1); p.add_argument("--dry-run",action="store_true")
        if name=="build-part": p.add_argument("--refresh-existing",action="store_true",help="Revalidate saved copy and safely shorten X; do not generate creative variants")
    args=parser.parse_args(argv); root=(root or codex_articles.ROOT).resolve()
    try:
        if args.command=="build-campaign": result=build_campaign(root,args.series_slug,dry_run=args.dry_run)
        elif args.command=="build-part":
            if args.part!=1: raise ValueError("v1 generates Part 1 only.")
            series,source=discover(root,args.series_slug); result=build_part(series,source,dry_run=args.dry_run,refresh_existing=args.refresh_existing)
        else: result=validate_package(root,args.series_slug,args.part)
        print(json.dumps(result,indent=2)); return 1 if result.get("errors") else 0
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}"); return 1


if __name__ == "__main__":
    raise SystemExit(main())
