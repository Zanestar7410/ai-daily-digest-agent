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


def test_web_search_collector_uses_high_reasoning() -> None:
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
    assert request["reasoning"] == {"effort": "high"}
    assert request["tools"][0]["type"] == "web_search"


def test_summarizer_uses_high_reasoning() -> None:
    client = FakeClient(
        [
            BatchSummary(
                entries=[
                    SummaryEntry(
                        url="https://openai.com/news/safety-guidance/",
                        summary="中文摘要",
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

    assert result["https://openai.com/news/safety-guidance/"] == "中文摘要"
    request = client.responses.calls[0]
    assert request["reasoning"] == {"effort": "high"}


def test_build_api_digest_document_and_save_json(tmp_path: Path) -> None:
    source = SearchSourceConfig(
        id="openai_news",
        name="OpenAI News",
        tier=0,
        domains=["openai.com"],
        query_hint="OpenAI official news",
    )

    class FakeCollector:
        def collect_items(self, *, sources, digest_time, lookback_days: int = 14):
            from ai_news_digest.models import SourceItem

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
            return {"https://openai.com/news/safety-guidance/": "中文摘要"}

    json_path = tmp_path / "latest_digest.json"
    document = build_api_digest_document(
        sources=[source],
        collector=FakeCollector(),
        summarizer=FakeSummarizer(),
        storage=DigestStorage(tmp_path / "state" / "digest.sqlite3"),
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        json_output_path=json_path,
    )

    assert len(document.entries) == 1
    assert json_path.exists()
    assert "中文摘要" in json_path.read_text(encoding="utf-8")

    other = tmp_path / "saved.json"
    save_digest_document(document=document, path=other)
    assert other.exists()
