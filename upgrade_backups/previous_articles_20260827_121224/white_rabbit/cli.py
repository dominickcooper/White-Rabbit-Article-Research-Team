from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_settings
from .gemini_provider import GeminiProvider
from .pipeline import SingleArticlePipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="white_rabbit", description="White Rabbit Report research/writing pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Verify configuration and Gemini connectivity")

    run = sub.add_parser("run", help="Research and produce one evidence-backed article")
    run.add_argument("topic")
    run.add_argument("--project", default=None, help="Workspace folder name")
    run.add_argument("--angle", default="", help="Optional thesis/angle to test, not assume")
    run.add_argument("--sources", type=Path, default=None, help="Folder containing private/local source files")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY is missing. Copy .env to .env and add the key.")
        return 2
    provider = GeminiProvider(settings.gemini_api_key, settings.model)
    if args.command == "doctor":
        print(f"Model: {settings.model}")
        print(provider.doctor())
        return 0
    pipeline = SingleArticlePipeline(settings, provider)
    pipeline.run(topic=args.topic, project=args.project, angle=args.angle, sources_folder=args.sources)
    return 0
