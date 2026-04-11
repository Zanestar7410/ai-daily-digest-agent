from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.api_server import build_api_response, render_dashboard_html
from ai_news_digest.models import SourceItem
from ai_news_digest.storage import DigestStorage


def build_event_storage(tmp_path: Path) -> DigestStorage:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    item = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI launches agent runtime",
        url="https://openai.com/news/agent-runtime/",
        published_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        excerpt="Runtime update.",
        topics=["coding-agent"],
        entities=["OpenAI", "Responses API"],
        event_type="product-release",
        confidence=0.88,
        why_it_matters="This changes coding-agent deployment choices.",
    )
    storage.upsert_items([item])
    run_id = storage.create_report_run(
        digest_date=datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
        pdf_path="output/2026-04-02.pdf",
        report_kind="daily",
        report_topic=None,
        tex_path="output/2026-04-02.tex",
    )
    storage.record_digest_entries(run_id, [(item, "Primary summary", False)])
    return storage


def test_build_api_response_events_endpoint_returns_json(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)

    status, payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/events?query=agent&event_type=product-release&entity=OpenAI&limit=5",
    )

    assert status == 200
    assert payload["count"] == 1
    assert payload["items"][0]["event_id"] == "https://openai.com/news/agent-runtime/"
    assert payload["items"][0]["confidence"] == 0.88


def test_build_api_response_entities_and_topics_endpoint(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)

    entity_status, entity_payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/entities?limit=5",
    )
    topic_status, topic_payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/topics?limit=5",
    )

    assert entity_status == 200
    assert entity_payload["items"][0]["name"] == "OpenAI"
    assert topic_status == 200
    assert topic_payload["items"][0]["name"] == "coding-agent"


def test_build_api_response_event_detail_endpoint(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)

    status, payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/events/detail?event_id=https%3A%2F%2Fopenai.com%2Fnews%2Fagent-runtime%2F",
    )

    assert status == 200
    assert payload["item"]["event_id"] == "https://openai.com/news/agent-runtime/"
    assert payload["item"]["why_it_matters"] == "This changes coding-agent deployment choices."


def test_render_dashboard_html_mentions_search_and_detail_panels() -> None:
    html = render_dashboard_html()

    assert "AI Event Explorer" in html
    assert "Event Search" in html
    assert "Entity Timeline" in html
    assert "Event Detail" in html
    assert "Research Reports" in html
    assert "Run Research" in html
    assert "/research/run" in html
    assert "/research/report" in html


def test_build_api_response_research_reports_endpoint(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)
    report_id = storage.save_research_report(
        report={
            "query": "recent OpenAI agent changes",
            "generated_at": datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
            "executive_summary": "Summary paragraph.",
            "plan": {
                "query": "recent OpenAI agent changes",
                "steps": [{"title": "Review product updates", "question": "Which product updates are most relevant?"}],
            },
            "key_findings": ["Finding one"],
            "source_event_ids": ["https://openai.com/news/agent-runtime/"],
            "open_questions": [],
        },
        markdown="# Research Report",
        output_path="output/research.md",
    )

    status, payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/research/reports?limit=5",
    )

    assert status == 200
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == report_id


def test_build_api_response_research_report_detail_endpoint(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)
    report_id = storage.save_research_report(
        report={
            "query": "recent OpenAI agent changes",
            "generated_at": datetime(2026, 4, 11, 10, 30, tzinfo=UTC),
            "executive_summary": "Summary paragraph.",
            "plan": {
                "query": "recent OpenAI agent changes",
                "steps": [{"title": "Review product updates", "question": "Which product updates are most relevant?"}],
            },
            "key_findings": ["Finding one"],
            "source_event_ids": ["https://openai.com/news/agent-runtime/"],
            "open_questions": [],
        },
        markdown="# Research Report",
        output_path="output/research.md",
    )

    status, payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path=f"/research/report?report_id={report_id}",
    )

    assert status == 200
    assert payload["item"]["id"] == report_id
    assert payload["item"]["query"] == "recent OpenAI agent changes"
    assert payload["item"]["markdown"] == "# Research Report"


def test_build_api_response_research_run_endpoint(tmp_path: Path) -> None:
    storage = build_event_storage(tmp_path)

    status, payload = build_api_response(
        storage=storage,
        method="GET",
        raw_path="/research/run?query=recent%20OpenAI%20agent%20changes&limit=5",
    )

    assert status == 200
    assert payload["item"]["query"] == "recent OpenAI agent changes"
    assert payload["item"]["markdown"].startswith("# Research Report")
