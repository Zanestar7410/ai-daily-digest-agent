import sys
from datetime import datetime
from pathlib import Path

from ai_news_digest import cli
from ai_news_digest.api_mode import SummaryEntry
from ai_news_digest.cli import build_parser
from ai_news_digest.models import HistoricalSearchMatch, SourceItem


def test_cli_parser_accepts_input_and_dry_run() -> None:
    parser = build_parser()

    args = parser.parse_args(["--input", "input/latest_digest.json", "--dry-run"])

    assert args.input == "input/latest_digest.json"
    assert args.dry_run is True
    assert args.mode == "render"


def test_cli_parser_accepts_api_mode() -> None:
    parser = build_parser()

    args = parser.parse_args(["--mode", "api", "--input", "input/generated.json"])

    assert args.mode == "api"
    assert args.input == "input/generated.json"


def test_cli_parser_accepts_history_query_filters() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--history-query", "agent", "--limit", "5", "--topic", "coding-agent"]
    )

    assert args.history_query == "agent"
    assert args.limit == 5
    assert args.topic == "coding-agent"


def test_cli_parser_accepts_live_query_and_topic_reports() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--live-query", "OpenAI agents", "--limit", "7", "--write-topic-reports"]
    )

    assert args.live_query == "OpenAI agents"
    assert args.limit == 7
    assert args.write_topic_reports is True


def test_cli_parser_accepts_live_summary_and_history_filters() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--live-query",
            "OpenAI agents",
            "--summarize-live-query",
            "--source",
            "OpenAI News",
            "--entity",
            "Responses API",
            "--date-from",
            "2026-04-01",
            "--date-to",
            "2026-04-10",
        ]
    )

    assert args.summarize_live_query is True
    assert args.source == "OpenAI News"
    assert args.entity == "Responses API"
    assert args.date_from == "2026-04-01"
    assert args.date_to == "2026-04-10"


def test_cli_parser_accepts_entity_timeline() -> None:
    parser = build_parser()

    args = parser.parse_args(["--entity-timeline", "OpenAI", "--limit", "4"])

    assert args.entity_timeline == "OpenAI"
    assert args.limit == 4


def test_cli_parser_accepts_event_query_filters() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--event-query",
            "agent",
            "--event-type",
            "product-release",
            "--entity",
            "OpenAI",
            "--sort-by",
            "confidence",
        ]
    )

    assert args.event_query == "agent"
    assert args.event_type == "product-release"
    assert args.entity == "OpenAI"
    assert args.sort_by == "confidence"


def test_cli_parser_accepts_backfill_and_api_server_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--backfill-events", "--serve-api", "--api-host", "127.0.0.1", "--api-port", "9000"]
    )

    assert args.backfill_events is True
    assert args.serve_api is True
    assert args.api_host == "127.0.0.1"
    assert args.api_port == 9000


def test_cli_parser_accepts_research_mode_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--research-query",
            "最近两周 OpenAI agent 相关变化",
            "--research-output",
            "output/research.md",
            "--research-live",
            "--limit",
            "6",
        ]
    )

    assert args.research_query == "最近两周 OpenAI agent 相关变化"
    assert args.research_output == "output/research.md"
    assert args.research_live is True
    assert args.limit == 6


def test_live_query_without_summary_flag_skips_summarizer(monkeypatch, capsys) -> None:
    class FakeCollector:
        def search_latest_items(self, *, query, sources, digest_time, limit, lookback_days=14):
            return [
                SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI ships coding agent runtime",
                    url="https://openai.com/news/coding-agent-runtime/",
                    published_at=digest_time,
                    excerpt="Official runtime note.",
                )
            ]

    def fail_if_called():
        raise AssertionError("Summarizer should not be created without --summarize-live-query")

    monkeypatch.setattr(cli, "OpenAIWebSearchCollector", lambda: FakeCollector())
    monkeypatch.setattr(cli, "OpenAISummarizer", fail_if_called)
    monkeypatch.setattr(
        cli,
        "load_search_registry",
        lambda path: [],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["ai-news-digest", "--live-query", "coding agent", "--limit", "3"],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "Summary:" not in captured.out
    assert "Official runtime note." in captured.out


def test_live_query_summary_flag_renders_summary_topics_entities_and_event_type(monkeypatch, capsys) -> None:
    class FakeCollector:
        def search_latest_items(self, *, query, sources, digest_time, limit, lookback_days=14):
            return [
                SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI ships coding agent runtime",
                    url="https://openai.com/news/coding-agent-runtime/",
                    published_at=digest_time,
                    excerpt="Official runtime note.",
                )
            ]

    class FakeSummarizer:
        def summarize_items(self, items):
            return {
                items[0].url: SummaryEntry(
                    url=items[0].url,
                    summary="Chinese summary.",
                    topics=["coding-agent", "agent-platform"],
                    entities=["OpenAI", "Responses API"],
                    event_type="product-release",
                )
            }

    monkeypatch.setattr(cli, "OpenAIWebSearchCollector", lambda: FakeCollector())
    monkeypatch.setattr(cli, "OpenAISummarizer", lambda: FakeSummarizer())
    monkeypatch.setattr(
        cli,
        "load_search_registry",
        lambda path: [],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-news-digest",
            "--live-query",
            "coding agent",
            "--limit",
            "3",
            "--summarize-live-query",
        ],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "Summary: Chinese summary." in captured.out
    assert "Topics: Coding Agent, Agent Platform" in captured.out
    assert "Entities: OpenAI, Responses API" in captured.out
    assert "Event Type: product-release" in captured.out


def test_entity_timeline_command_formats_results(monkeypatch, capsys) -> None:
    class FakeStorage:
        def list_entity_timeline(self, *, entity, limit):
            assert entity == "OpenAI"
            assert limit == 3
            return [
                HistoricalSearchMatch(
                    item=SourceItem(
                        source_id="openai_news",
                        source_name="OpenAI News",
                        source_tier=0,
                        title="OpenAI launches agent runtime",
                        url="https://openai.com/news/agent-runtime/",
                        published_at=datetime(2026, 4, 2, 9, 0),
                        excerpt="Runtime update.",
                        topics=["coding-agent"],
                        entities=["OpenAI", "Responses API"],
                        event_type="product-release",
                    )
                )
            ]

    monkeypatch.setattr(cli, "DigestStorage", lambda path: FakeStorage())
    monkeypatch.setattr(
        sys,
        "argv",
        ["ai-news-digest", "--entity-timeline", "OpenAI", "--limit", "3"],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "OpenAI launches agent runtime" in captured.out
    assert "Entities: OpenAI, Responses API" in captured.out
    assert "Event Type: product-release" in captured.out


def test_event_query_command_formats_results(monkeypatch, capsys) -> None:
    class FakeStorage:
        def save_research_report(self, *, report, markdown, output_path=None):
            return 1

        def search_events(self, *, query, topic=None, source=None, entity=None, event_type=None, date_from=None, date_to=None, sort_by="published_at", limit=20):
            assert query == "agent"
            assert entity == "OpenAI"
            assert event_type == "product-release"
            assert sort_by == "published_at"
            assert limit == 3
            from ai_news_digest.models import EventRecord

            return [
                EventRecord(
                    event_id="https://openai.com/news/agent-runtime/",
                    title="OpenAI launches agent runtime",
                    summary="Primary summary",
                    event_type="product-release",
                    source_name="OpenAI News",
                    source_tier=0,
                    published_at=datetime(2026, 4, 2, 9, 0),
                    url="https://openai.com/news/agent-runtime/",
                    topics=["coding-agent"],
                    entities=["OpenAI", "Responses API"],
                    excerpt="Runtime update.",
                    confidence=0.88,
                    why_it_matters="This changes coding-agent deployment choices.",
                )
            ]

    monkeypatch.setattr(cli, "DigestStorage", lambda path: FakeStorage())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-news-digest",
            "--event-query",
            "agent",
            "--event-type",
            "product-release",
            "--entity",
            "OpenAI",
            "--limit",
            "3",
        ],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "OpenAI launches agent runtime" in captured.out
    assert "Summary: Primary summary" in captured.out
    assert "Entities: OpenAI, Responses API" in captured.out
    assert "Confidence: 0.88" in captured.out
    assert "Why It Matters: This changes coding-agent deployment choices." in captured.out


def test_research_query_command_formats_markdown_report(monkeypatch, capsys) -> None:
    class FakeStorage:
        def save_research_report(self, *, report, markdown, output_path=None):
            return 1

        def search_events(self, *, query, topic=None, source=None, entity=None, event_type=None, date_from=None, date_to=None, sort_by="published_at", limit=20):
            assert query == "最近两周 OpenAI agent 相关变化"
            from ai_news_digest.models import EventRecord

            return [
                EventRecord(
                    event_id="https://openai.com/news/agent-runtime/",
                    title="OpenAI launches agent runtime",
                    summary="Primary summary",
                    event_type="product-release",
                    source_name="OpenAI News",
                    source_tier=0,
                    published_at=datetime(2026, 4, 2, 9, 0),
                    url="https://openai.com/news/agent-runtime/",
                    topics=["coding-agent"],
                    entities=["OpenAI", "Responses API"],
                    excerpt="Runtime update.",
                    confidence=0.88,
                    why_it_matters="This changes coding-agent deployment choices.",
                )
            ]

    monkeypatch.setattr(cli, "DigestStorage", lambda path: FakeStorage())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-news-digest",
            "--research-query",
            "最近两周 OpenAI agent 相关变化",
            "--limit",
            "3",
        ],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "# Research Report" in captured.out
    assert "最近两周 OpenAI agent 相关变化" in captured.out
    assert "https://openai.com/news/agent-runtime/" in captured.out


def test_research_query_live_flag_merges_live_events(monkeypatch, capsys) -> None:
    class FakeStorage:
        def save_research_report(self, *, report, markdown, output_path=None):
            return 1

        def search_events(self, **kwargs):
            from ai_news_digest.models import EventRecord

            return [
                EventRecord(
                    event_id="https://openai.com/news/agent-runtime/",
                    title="Stored event",
                    summary="Stored summary",
                    event_type="product-release",
                    source_name="OpenAI News",
                    source_tier=0,
                    published_at=datetime(2026, 4, 2, 9, 0),
                    url="https://openai.com/news/agent-runtime/",
                    topics=["coding-agent"],
                    entities=["OpenAI"],
                    confidence=0.8,
                    why_it_matters="Stored why.",
                )
            ]

    class FakeCollector:
        def search_latest_items(self, *, query, sources, digest_time, limit, lookback_days=14):
            return [
                SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="Live event",
                    url="https://openai.com/news/live-event/",
                    published_at=digest_time,
                    excerpt="Live excerpt",
                )
            ]

    class FakeSummarizer:
        def summarize_items(self, items):
            return {
                items[0].url: SummaryEntry(
                    url=items[0].url,
                    summary="Live summary",
                    topics=["agent-platform"],
                    entities=["OpenAI"],
                    event_type="product-release",
                    confidence=0.9,
                    why_it_matters="Live why.",
                )
            }

    class FakeBuilder:
        def __init__(self, *, planner, writer):
            self.planner = planner
            self.writer = writer

        def build(self, *, query, events, output_path=None):
            assert len(events) == 2
            from ai_news_digest.research_mode import ResearchPlan, ResearchPlanStep, ResearchReport

            report = ResearchReport(
                query=query,
                generated_at=datetime(2026, 4, 11, 10, 30),
                executive_summary="总结。",
                plan=ResearchPlan(
                    query=query,
                    steps=[ResearchPlanStep(title="整理", question="看变化")],
                ),
                key_findings=["发现"],
                source_event_ids=[event.event_id for event in events],
                open_questions=[],
            )
            if output_path is not None:
                output_path.write_text("x", encoding="utf-8")
            return report

    monkeypatch.setattr(cli, "DigestStorage", lambda path: FakeStorage())
    monkeypatch.setattr(cli, "OpenAIWebSearchCollector", lambda: FakeCollector())
    monkeypatch.setattr(cli, "OpenAISummarizer", lambda: FakeSummarizer())
    monkeypatch.setattr(cli, "ResearchReportBuilder", FakeBuilder)
    monkeypatch.setattr(cli, "load_search_registry", lambda path: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-news-digest",
            "--research-query",
            "最近两周 OpenAI agent 相关变化",
            "--research-live",
            "--limit",
            "3",
        ],
    )

    result = cli.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "# Research Report" in captured.out
