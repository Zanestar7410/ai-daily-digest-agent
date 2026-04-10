from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path

from ai_news_digest.api_mode import OpenAIWebSearchCollector, OpenAISummarizer, build_api_digest_document
from ai_news_digest.config import load_search_registry
from ai_news_digest.digest_document import load_digest_document
from ai_news_digest.render_pipeline import DigestRenderPipeline
from ai_news_digest.storage import DigestStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-news-digest")
    parser.add_argument("--mode", choices=["render", "api"], default="render", help="Execution mode")
    parser.add_argument("--input", default="input/latest_digest.json", help="Structured digest JSON path")
    parser.add_argument("--config", default="config/search_sources.json", help="Search registry path for API mode")
    parser.add_argument("--dry-run", action="store_true", help="Skip PDF compilation")
    parser.add_argument("--state-dir", default="state", help="State directory")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    return parser


def resolve_digest_time_from_path(path: Path) -> datetime:
    local_tz = datetime.now().astimezone().tzinfo
    return datetime.combine(datetime.now().date(), time(hour=10, minute=30), tzinfo=local_tz)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if args.mode == "api":
        document = build_api_digest_document(
            sources=load_search_registry(Path(args.config)),
            collector=OpenAIWebSearchCollector(),
            summarizer=OpenAISummarizer(),
            storage=DigestStorage(Path(args.state_dir) / "digest.sqlite3"),
            digest_time=resolve_digest_time_from_path(input_path),
            json_output_path=input_path,
        )
    else:
        document = load_digest_document(input_path)

    pipeline = DigestRenderPipeline(
        storage=DigestStorage(Path(args.state_dir) / "digest.sqlite3"),
        output_dir=Path(args.output_dir),
    )
    result = pipeline.run(document=document, dry_run=args.dry_run)
    print(f"Selected {result.selected_count} items.")
    print(f"TEX: {result.tex_path}")
    if result.pdf_path is not None:
        print(f"PDF: {result.pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
