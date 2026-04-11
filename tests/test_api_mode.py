from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.api_mode import (
    BatchSummary,
    OpenAISummarizer,
    OpenAIWebSearchCollector,
    SearchBatch,
    SearchResultEntry,
    SummaryEntry,
    build_api_digest_document,
    save_digest_document,
)
from ai_news_digest.models import SearchSourceConfig, SourceItem
from ai_news_digest.storage import DigestStorage


class FakeResponses:
    def __init__(self, parsed_objects: list[object]) -> None:
        self.parsed_objects = parsed_objects
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        parsed = self.parsed_objects.pop(0)
        return type("FakeResponse", (), {"output_parsed": parsed})()


class FakeClient:
    def __init__(self, parsed_objects: list[object]) -> None:
        self.responses = FakeResponses(parsed_objects)


def test_web_search_collector_uses_medium_reasoning() -> None:
    source = SearchSourceConfig(
        id="openai_news",
        name="OpenAI News",
        tier=0,
        domains=["openai.com"],
        query_hint="OpenAI official news",
    )
    client = FakeClient(
        [
            SearchBatch(
                entries=[
                    SearchResultEntry(
                        title="OpenAI updates safety guidance",
                        url="https://openai.com/news/safety-guidance/",
                        published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
                        excerpt="Official summary.",
                    )
                ]
            )
        ]
    )
    collector = OpenAIWebSearchCollector(client=client)

    items = collector.collect_items(
        sources=[source],
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
    )

    assert items[0].title == "OpenAI updates safety guidance"
    request = client.responses.calls[0]
    assert request["reasoning"] == {"effort": "medium"}
    assert request["tools"][0]["type"] == "web_search"


def test_summarizer_uses_medium_reasoning() -> None:
    client = FakeClient(
        [
            BatchSummary(
                entries=[
                    SummaryEntry(
                        url="https://openai.com/news/safety-guidance/",
                        summary="summary",
                        topics=["safety-governance"],
                        entities=["OpenAI"],
                        event_type="policy-update",
                        confidence=0.91,
                        why_it_matters="This affects enterprise rollout decisions.",
                    )
                ]
            )
        ]
    )
    summarizer = OpenAISummarizer(client=client)
    item = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI updates safety guidance",
        url="https://openai.com/news/safety-guidance/",
        published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
        excerpt="Official summary.",
    )

    result = summarizer.summarize_items([item])

    assert result["https://openai.com/news/safety-guidance/"].summary == "summary"
    assert result["https://openai.com/news/safety-guidance/"].topics == [
        "safety-governance"
    ]
    assert result["https://openai.com/news/safety-guidance/"].entities == ["OpenAI"]
    assert result["https://openai.com/news/safety-guidance/"].event_type == "policy-update"
    assert result["https://openai.com/news/safety-guidance/"].confidence == 0.91
    assert (
        result["https://openai.com/news/safety-guidance/"].why_it_matters
        == "This affects enterprise rollout decisions."
    )
    request = client.responses.calls[0]
    assert request["reasoning"] == {"effort": "medium"}


def test_web_search_collector_supports_live_query_and_sorts_newest_first() -> None:
    sources = [
        SearchSourceConfig(
            id="openai_news",
            name="OpenAI News",
            tier=0,
            domains=["openai.com"],
            query_hint="OpenAI official news",
        ),
        SearchSourceConfig(
            id="github_community_ai",
            name="GitHub Community AI",
            tier=2,
            domains=["github.com"],
            query_hint="High-signal GitHub AI posts",
        ),
    ]
    client = FakeClient(
        [
            SearchBatch(
                entries=[
                    SearchResultEntry(
                        title="OpenAI ships coding agent API",
                        url="https://openai.com/news/coding-agent-api/",
                        published_at=datetime(2026, 4, 5, 8, 0, tzinfo=UTC),
                        excerpt="Official launch note.",
                    )
                ]
            ),
            SearchBatch(
                entries=[
                    SearchResultEntry(
                        title="Popular coding agent repo adds runtime",
                        url="https://github.com/example/coding-agent/releases/tag/v1",
                        published_at=datetime(2026, 4, 5, 9, 0, tzinfo=UTC),
                        excerpt="Community release note.",
                    )
                ]
            ),
        ]
    )
    collector = OpenAIWebSearchCollector(client=client)

    items = collector.search_latest_items(
        query="coding agent",
        sources=sources,
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        limit=5,
    )

    assert [item.url for item in items] == [
        "https://github.com/example/coding-agent/releases/tag/v1",
        "https://openai.com/news/coding-agent-api/",
    ]
    request = client.responses.calls[0]
    assert "Search query: coding agent" in request["input"][1]["content"]


def test_build_api_digest_document_dry_run_does_not_persist_state(tmp_path: Path) -> None:
    source = SearchSourceConfig(
        id="openai_news",
        name="OpenAI News",
        tier=0,
        domains=["openai.com"],
        query_hint="OpenAI official news",
    )

    class FakeCollector:
        def collect_items(self, *, sources, digest_time, lookback_days: int = 14):
            return [
                SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI updates safety guidance",
                    url="https://openai.com/news/safety-guidance/",
                    published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
                    excerpt="Official summary.",
                )
            ]

    class FakeSummarizer:
        def summarize_items(self, items):
            return {
                "https://openai.com/news/safety-guidance/": SummaryEntry(
                    url="https://openai.com/news/safety-guidance/",
                    summary="summary",
                    topics=["safety-governance"],
                    entities=["OpenAI"],
                    event_type="policy-update",
                    confidence=0.91,
                    why_it_matters="This affects enterprise rollout decisions.",
                )
            }

    json_path = tmp_path / "latest_digest.json"
    document = build_api_digest_document(
        sources=[source],
        collector=FakeCollector(),
        summarizer=FakeSummarizer(),
        storage=DigestStorage(tmp_path / "state" / "digest.sqlite3"),
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        dry_run=True,
        json_output_path=json_path,
    )

    assert len(document.entries) == 1
    assert json_path.exists()
    assert "summary" in json_path.read_text(encoding="utf-8")
    assert not (tmp_path / "state" / "digest.sqlite3").exists()
    assert document.entries[0].item.topics == ["safety-governance"]
    assert document.entries[0].item.entities == ["OpenAI"]
    assert document.entries[0].item.event_type == "policy-update"
    assert document.entries[0].item.confidence == 0.91
    assert (
        document.entries[0].item.why_it_matters
        == "This affects enterprise rollout decisions."
    )

    other = tmp_path / "saved.json"
    save_digest_document(document=document, path=other)
    assert other.exists()
