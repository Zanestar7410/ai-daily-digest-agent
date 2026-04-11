from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.models import EventRecord
from ai_news_digest.research_mode import (
    ResearchPlan,
    ResearchPlanStep,
    ResearchReport,
    ResearchReportBuilder,
    render_research_markdown,
)
from ai_news_digest.storage import DigestStorage


def build_event(event_id: str, title: str, *, summary: str, published_at: datetime) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        title=title,
        summary=summary,
        event_type="product-release",
        source_name="OpenAI News",
        source_tier=0,
        published_at=published_at,
        url=event_id,
        topics=["coding-agent"],
        entities=["OpenAI", "Responses API"],
        excerpt="Runtime update.",
        confidence=0.88,
        why_it_matters="This changes coding-agent deployment choices.",
    )


def test_render_research_markdown_includes_plan_findings_and_sources() -> None:
    report = ResearchReport(
        query="recent OpenAI agent changes",
        generated_at=datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
        executive_summary="Summary paragraph.",
        plan=ResearchPlan(
            query="recent OpenAI agent changes",
            steps=[
                ResearchPlanStep(
                    title="Review product updates",
                    question="Which product updates are most relevant?",
                )
            ],
        ),
        key_findings=["Finding one", "Finding two"],
        evidence_highlights=["Evidence one"],
        comparison_notes=["Compare OpenAI product and policy signals."],
        source_event_ids=["https://openai.com/news/agent-runtime/"],
        open_questions=["Need more evidence from other vendors."],
        verification_notes=["Only one first-party source is currently represented."],
    )

    markdown = render_research_markdown(report)

    assert "# Research Report" in markdown
    assert "recent OpenAI agent changes" in markdown
    assert "Finding one" in markdown
    assert "Evidence one" in markdown
    assert "Compare OpenAI product and policy signals." in markdown
    assert "Only one first-party source is currently represented." in markdown
    assert "https://openai.com/news/agent-runtime/" in markdown


def test_research_report_builder_uses_planner_and_writer() -> None:
    class FakePlanner:
        def build_plan(self, *, query: str, events: list[EventRecord]) -> ResearchPlan:
            assert query == "recent OpenAI agent changes"
            assert len(events) == 2
            return ResearchPlan(
                query=query,
                steps=[
                    ResearchPlanStep(
                        title="Review product updates",
                        question="Which product updates are most relevant?",
                    )
                ],
            )

    class FakeWriter:
        def build_report(
            self,
            *,
            query: str,
            plan: ResearchPlan,
            events: list[EventRecord],
        ) -> ResearchReport:
            assert plan.steps[0].title == "Review product updates"
            return ResearchReport(
                query=query,
                generated_at=datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
                executive_summary="Summary paragraph.",
                plan=plan,
                key_findings=["Finding one"],
                source_event_ids=[events[0].event_id],
                open_questions=[],
            )

    builder = ResearchReportBuilder(planner=FakePlanner(), writer=FakeWriter())
    report = builder.build(
        query="recent OpenAI agent changes",
        events=[
            build_event(
                "https://openai.com/news/agent-runtime/",
                "OpenAI launches agent runtime",
                summary="Primary summary",
                published_at=datetime(2026, 4, 2, tzinfo=UTC),
            ),
            build_event(
                "https://openai.com/news/agent-safety/",
                "OpenAI agent safety update",
                summary="Safety summary",
                published_at=datetime(2026, 4, 1, tzinfo=UTC),
            ),
        ],
    )

    assert report.key_findings == ["Finding one"]
    assert report.source_event_ids == ["https://openai.com/news/agent-runtime/"]
    assert report.evidence_highlights
    assert report.comparison_notes


def test_research_report_builder_writes_markdown_output(tmp_path: Path) -> None:
    class FakePlanner:
        def build_plan(self, *, query: str, events: list[EventRecord]) -> ResearchPlan:
            return ResearchPlan(
                query=query,
                steps=[
                    ResearchPlanStep(
                        title="Review product updates",
                        question="Which product updates are most relevant?",
                    )
                ],
            )

    class FakeWriter:
        def build_report(
            self,
            *,
            query: str,
            plan: ResearchPlan,
            events: list[EventRecord],
        ) -> ResearchReport:
            return ResearchReport(
                query=query,
                generated_at=datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
                executive_summary="Summary paragraph.",
                plan=plan,
                key_findings=["Finding one"],
                source_event_ids=[events[0].event_id],
                open_questions=[],
            )

    builder = ResearchReportBuilder(planner=FakePlanner(), writer=FakeWriter())
    output_path = tmp_path / "research.md"

    report = builder.build(
        query="recent OpenAI agent changes",
        events=[
            build_event(
                "https://openai.com/news/agent-runtime/",
                "OpenAI launches agent runtime",
                summary="Primary summary",
                published_at=datetime(2026, 4, 2, tzinfo=UTC),
            )
        ],
        output_path=output_path,
    )

    assert report.query == "recent OpenAI agent changes"
    assert output_path.exists()
    assert "Summary paragraph." in output_path.read_text(encoding="utf-8")


def test_storage_persists_research_report_record(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    report = ResearchReport(
        query="recent OpenAI agent changes",
        generated_at=datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
        executive_summary="Summary paragraph.",
        plan=ResearchPlan(
            query="recent OpenAI agent changes",
            steps=[
                ResearchPlanStep(
                    title="Review product updates",
                    question="Which product updates are most relevant?",
                )
            ],
        ),
        key_findings=["Finding one"],
        source_event_ids=["https://openai.com/news/agent-runtime/"],
        open_questions=[],
    )

    report_id = storage.save_research_report(
        report=report,
        markdown="# Research Report",
        output_path="output/research.md",
    )
    records = storage.list_research_reports(limit=10)
    loaded = storage.get_research_report(report_id=report_id)

    assert report_id >= 1
    assert records[0]["query"] == "recent OpenAI agent changes"
    assert loaded is not None
    assert loaded["markdown"] == "# Research Report"
    assert loaded["output_path"] == "output/research.md"
    assert "evidence_highlights" in loaded
