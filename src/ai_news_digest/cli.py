from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path

from ai_news_digest.api_server import serve_api
from ai_news_digest.api_mode import SummaryEntry, OpenAIWebSearchCollector, OpenAISummarizer, build_api_digest_document
from ai_news_digest.config import load_search_registry
from ai_news_digest.digest_document import load_digest_document
from ai_news_digest.models import EventRecord, HistoricalSearchMatch, SourceItem
from ai_news_digest.research_mode import (
    ResearchReportBuilder,
    RuleBasedResearchPlanner,
    RuleBasedResearchWriter,
    render_research_markdown,
    run_research_mode,
)
from ai_news_digest.render_pipeline import DigestRenderPipeline
from ai_news_digest.storage import DigestStorage
from ai_news_digest.topics import format_topic_label


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-news-digest")
    parser.add_argument("--mode", choices=["render", "api"], default="render", help="Execution mode")
    parser.add_argument("--input", default="input/latest_digest.json", help="Structured digest JSON path")
    parser.add_argument("--config", default="config/search_sources.json", help="Search registry path for API mode")
    parser.add_argument("--dry-run", action="store_true", help="Skip PDF compilation")
    parser.add_argument("--state-dir", default="state", help="State directory")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--history-query", help="Search previously stored items")
    parser.add_argument("--event-query", help="Search persisted extracted events")
    parser.add_argument("--live-query", help="Search recent live updates by keyword")
    parser.add_argument("--research-query", help="Generate a research report from persisted events")
    parser.add_argument("--entity-timeline", help="Show a reverse-chronological timeline for one entity")
    parser.add_argument("--backfill-events", action="store_true", help="Backfill persisted events from historical digest entries")
    parser.add_argument("--serve-api", action="store_true", help="Serve a lightweight JSON API for events, entities, and topics")
    parser.add_argument("--api-host", default="127.0.0.1", help="API server host")
    parser.add_argument("--api-port", type=int, default=8000, help="API server port")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of query results")
    parser.add_argument("--topic", help="Filter history results by topic")
    parser.add_argument("--source", help="Filter history results by source name")
    parser.add_argument("--entity", help="Filter history results by entity name")
    parser.add_argument("--event-type", help="Filter event results by event type")
    parser.add_argument("--date-from", help="Filter history results on or after YYYY-MM-DD")
    parser.add_argument("--date-to", help="Filter history results on or before YYYY-MM-DD")
    parser.add_argument("--research-output", help="Optional markdown output path for research mode")
    parser.add_argument("--research-live", action="store_true", help="Reserve a future live-search enrichment path for research mode")
    parser.add_argument(
        "--sort-by",
        choices=["published_at", "confidence"],
        default="published_at",
        help="Event query sort order",
    )
    parser.add_argument(
        "--summarize-live-query",
        action="store_true",
        help="Generate Chinese summaries plus topics/entities for live query results",
    )
    parser.add_argument(
        "--write-topic-reports",
        action="store_true",
        help="Write one additional report per detected topic",
    )
    return parser


def format_history_match(index: int, match: HistoricalSearchMatch) -> str:
    lines = [
        f"{index}. {match.item.title}",
        f"   Published: {match.item.published_at.isoformat()}",
        f"   Source: {match.item.source_name}",
    ]
    if match.item.topics:
        lines.append(
            "   Topics: " + ", ".join(format_topic_label(topic) for topic in match.item.topics)
        )
    if match.item.entities:
        lines.append("   Entities: " + ", ".join(match.item.entities))
    if match.item.event_type:
        lines.append(f"   Event Type: {match.item.event_type}")
    if match.item.confidence > 0:
        lines.append(f"   Confidence: {match.item.confidence:.2f}")
    if match.item.why_it_matters:
        lines.append(f"   Why It Matters: {match.item.why_it_matters}")
    if match.summary:
        lines.append(f"   Summary: {match.summary}")
    lines.append(f"   URL: {match.item.url}")
    return "\n".join(lines)


def format_live_query_result(
    index: int,
    item: SourceItem,
    summary_entry: SummaryEntry | None = None,
) -> str:
    lines = [
        f"{index}. {item.title}",
        f"   Published: {item.published_at.isoformat()}",
        f"   Source: {item.source_name}",
    ]
    if summary_entry is not None:
        if summary_entry.topics:
            lines.append(
                "   Topics: "
                + ", ".join(format_topic_label(topic) for topic in summary_entry.topics)
            )
        if summary_entry.entities:
            lines.append("   Entities: " + ", ".join(summary_entry.entities))
        if summary_entry.event_type:
            lines.append(f"   Event Type: {summary_entry.event_type}")
        if summary_entry.confidence > 0:
            lines.append(f"   Confidence: {summary_entry.confidence:.2f}")
        if summary_entry.why_it_matters:
            lines.append(f"   Why It Matters: {summary_entry.why_it_matters}")
        lines.append(f"   Summary: {summary_entry.summary}")
    elif item.excerpt:
        lines.append(f"   Excerpt: {item.excerpt}")
    lines.append(f"   URL: {item.url}")
    return "\n".join(lines)


def format_event_record(index: int, event: EventRecord) -> str:
    lines = [
        f"{index}. {event.title}",
        f"   Published: {event.published_at.isoformat()}",
        f"   Source: {event.source_name}",
    ]
    if event.topics:
        lines.append("   Topics: " + ", ".join(format_topic_label(topic) for topic in event.topics))
    if event.entities:
        lines.append("   Entities: " + ", ".join(event.entities))
    if event.event_type:
        lines.append(f"   Event Type: {event.event_type}")
    if event.confidence > 0:
        lines.append(f"   Confidence: {event.confidence:.2f}")
    if event.why_it_matters:
        lines.append(f"   Why It Matters: {event.why_it_matters}")
    lines.append(f"   Summary: {event.summary}")
    lines.append(f"   URL: {event.url}")
    return "\n".join(lines)


def format_research_report(markdown: str) -> str:
    return markdown


def build_live_research_events(
    *,
    query: str,
    limit: int,
    digest_time: datetime,
    config_path: Path,
) -> list[EventRecord]:
    collector = OpenAIWebSearchCollector()
    items = collector.search_latest_items(
        query=query,
        sources=load_search_registry(config_path),
        digest_time=digest_time,
        limit=limit,
    )
    if not items:
        return []
    summary_map = OpenAISummarizer().summarize_items(items)
    return [
        EventRecord(
            event_id=item.url,
            title=item.title,
            summary=summary_map[item.url].summary,
            event_type=summary_map[item.url].event_type,
            source_name=item.source_name,
            source_tier=item.source_tier,
            published_at=item.published_at,
            url=item.url,
            topics=summary_map[item.url].topics,
            entities=summary_map[item.url].entities,
            excerpt=item.excerpt,
            confidence=summary_map[item.url].confidence,
            why_it_matters=summary_map[item.url].why_it_matters,
        )
        for item in items
    ]


def resolve_digest_time_from_path(path: Path) -> datetime:
    local_tz = datetime.now().astimezone().tzinfo
    return datetime.combine(datetime.now().date(), time(hour=10, minute=30), tzinfo=local_tz)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    storage = DigestStorage(Path(args.state_dir) / "digest.sqlite3")
    if args.research_query:
        events = storage.search_events(
            query=args.research_query,
            topic=args.topic,
            source=args.source,
            entity=args.entity,
            event_type=args.event_type,
            date_from=args.date_from,
            date_to=args.date_to,
            sort_by=args.sort_by,
            limit=args.limit,
        )
        if args.research_live:
            live_events = build_live_research_events(
                query=args.research_query,
                limit=args.limit,
                digest_time=resolve_digest_time_from_path(input_path),
                config_path=Path(args.config),
            )
            merged_events: dict[str, EventRecord] = {event.event_id: event for event in events}
            for event in live_events:
                merged_events[event.event_id] = event
            events = list(merged_events.values())
        builder = ResearchReportBuilder(
            planner=RuleBasedResearchPlanner(),
            writer=RuleBasedResearchWriter(),
        )
        output_path = Path(args.research_output) if args.research_output else None
        report, markdown = run_research_mode(
            query=args.research_query,
            events=events,
            output_path=output_path,
            planner=builder.planner,
            writer=builder.writer,
        )
        storage.save_research_report(
            report=report,
            markdown=markdown,
            output_path=str(output_path) if output_path is not None else None,
        )
        print(format_research_report(markdown))
        return 0

    if args.backfill_events:
        processed = storage.backfill_events()
        print(f"Backfilled {processed} events.")
        if not args.serve_api:
            return 0

    if args.serve_api:
        print(f"Serving API on http://{args.api_host}:{args.api_port}")
        serve_api(storage=storage, host=args.api_host, port=args.api_port)
        return 0

    if args.event_query:
        events = storage.search_events(
            query=args.event_query,
            topic=args.topic,
            source=args.source,
            entity=args.entity,
            event_type=args.event_type,
            date_from=args.date_from,
            date_to=args.date_to,
            sort_by=args.sort_by,
            limit=args.limit,
        )
        for index, event in enumerate(events, start=1):
            print(format_event_record(index, event))
        return 0

    if args.entity_timeline:
        matches = storage.list_entity_timeline(entity=args.entity_timeline, limit=args.limit)
        for index, match in enumerate(matches, start=1):
            print(format_history_match(index, match))
        return 0

    if args.history_query:
        matches = storage.search_items(
            query=args.history_query,
            topic=args.topic,
            source=args.source,
            entity=args.entity,
            date_from=args.date_from,
            date_to=args.date_to,
            limit=args.limit,
        )
        for index, match in enumerate(matches, start=1):
            print(format_history_match(index, match))
        return 0

    if args.live_query:
        collector = OpenAIWebSearchCollector()
        items = collector.search_latest_items(
            query=args.live_query,
            sources=load_search_registry(Path(args.config)),
            digest_time=resolve_digest_time_from_path(input_path),
            limit=args.limit,
        )
        summary_map: dict[str, SummaryEntry] = {}
        if args.summarize_live_query and items:
            summary_map = OpenAISummarizer().summarize_items(items)
        for index, item in enumerate(items, start=1):
            print(format_live_query_result(index, item, summary_map.get(item.url)))
        return 0

    if args.mode == "api":
        document = build_api_digest_document(
            sources=load_search_registry(Path(args.config)),
            collector=OpenAIWebSearchCollector(),
            summarizer=OpenAISummarizer(),
            storage=storage,
            digest_time=resolve_digest_time_from_path(input_path),
            dry_run=args.dry_run,
            json_output_path=input_path,
        )
    else:
        document = load_digest_document(input_path)

    pipeline = DigestRenderPipeline(
        storage=storage,
        output_dir=Path(args.output_dir),
    )
    result = pipeline.run(
        document=document,
        dry_run=args.dry_run,
        write_topic_reports=args.write_topic_reports,
    )
    print(f"Selected {result.selected_count} items.")
    print(f"TEX: {result.tex_path}")
    if result.pdf_path is not None:
        print(f"PDF: {result.pdf_path}")
    for topic, tex_path in result.topic_tex_paths.items():
        print(f"TOPIC TEX [{topic}]: {tex_path}")
        if result.topic_pdf_paths.get(topic) is not None:
            print(f"TOPIC PDF [{topic}]: {result.topic_pdf_paths[topic]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
