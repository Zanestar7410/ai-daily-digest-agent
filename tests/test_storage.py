from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from ai_news_digest.models import SourceItem
from ai_news_digest.storage import DigestStorage


def build_item(
    url: str,
    published_at: datetime,
    *,
    topics: list[str] | None = None,
    entities: list[str] | None = None,
    event_type: str = "",
    confidence: float = 0.0,
    why_it_matters: str = "",
) -> SourceItem:
    return SourceItem(
        source_id="google_ai_blog",
        source_name="Google AI Blog",
        source_tier=0,
        title=url.rsplit("/", maxsplit=1)[-1],
        url=url,
        published_at=published_at,
        excerpt="Sample excerpt",
        topics=topics or [],
        entities=entities or [],
        event_type=event_type,
        confidence=confidence,
        why_it_matters=why_it_matters,
    )


def test_storage_upserts_items_and_suppresses_duplicate_urls(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()

    first = build_item("https://blog.google/item-1", datetime(2026, 3, 31, tzinfo=UTC))
    duplicate = build_item("https://blog.google/item-1", datetime(2026, 3, 31, tzinfo=UTC))

    storage.upsert_items([first, duplicate])

    items = storage.list_unselected_items()
    assert len(items) == 1
    assert items[0].url == "https://blog.google/item-1"


def test_storage_tracks_previously_selected_items(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    item = build_item("https://blog.google/item-2", datetime(2026, 3, 30, tzinfo=UTC))
    storage.upsert_items([item])

    run_id = storage.create_digest_run(
        digest_date=datetime(2026, 4, 1, 10, 30, tzinfo=UTC),
        pdf_path="output/2026-04-01.pdf",
    )
    storage.record_digest_entries(run_id, [(item, "summary", False)])

    assert storage.list_unselected_items() == []


def test_storage_lists_selected_urls(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    item = build_item("https://blog.google/item-3", datetime(2026, 3, 30, tzinfo=UTC))
    storage.upsert_items([item])

    run_id = storage.create_digest_run(
        digest_date=datetime(2026, 4, 1, 10, 30, tzinfo=UTC),
        pdf_path="output/2026-04-01.pdf",
    )
    storage.record_digest_entries(run_id, [(item, "summary", False)])

    assert storage.list_selected_urls() == {"https://blog.google/item-3"}


def test_storage_searches_historical_items_with_topic_filter_newest_first(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    older = build_item(
        "https://blog.google/agent-old",
        datetime(2026, 3, 28, tzinfo=UTC),
        topics=["coding-agent"],
    )
    newer = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI coding agent runtime",
        url="https://openai.com/news/coding-agent-runtime/",
        published_at=datetime(2026, 3, 30, tzinfo=UTC),
        excerpt="Agent runtime update.",
        topics=["coding-agent", "agent-platform"],
    )
    storage.upsert_items([older, newer])

    matches = storage.search_items(query="agent", topic="coding-agent", limit=10)

    assert [match.item.url for match in matches] == [
        "https://openai.com/news/coding-agent-runtime/",
        "https://blog.google/agent-old",
    ]
    assert matches[0].item.topics == ["coding-agent", "agent-platform"]


def test_storage_search_filters_by_source_date_range_and_entity(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    storage.upsert_items(
        [
            SourceItem(
                source_id="openai_news",
                source_name="OpenAI News",
                source_tier=0,
                title="OpenAI ships coding agent runtime",
                url="https://openai.com/news/coding-agent-runtime/",
                published_at=datetime(2026, 3, 30, tzinfo=UTC),
                excerpt="Agent runtime update.",
                topics=["coding-agent"],
                entities=["OpenAI", "Responses API"],
                event_type="product-release",
            ),
            SourceItem(
                source_id="github_community_ai",
                source_name="GitHub Community AI",
                source_tier=2,
                title="Coding agent repo update",
                url="https://github.com/example/coding-agent/releases/tag/v2",
                published_at=datetime(2026, 3, 30, tzinfo=UTC),
                excerpt="Community release.",
                topics=["coding-agent"],
                entities=["Example Org"],
                event_type="open-source-release",
            ),
            SourceItem(
                source_id="openai_news",
                source_name="OpenAI News",
                source_tier=0,
                title="OpenAI agents archive",
                url="https://openai.com/news/agents-archive/",
                published_at=datetime(2026, 3, 25, tzinfo=UTC),
                excerpt="Older archive.",
                topics=["agent-platform"],
                entities=["OpenAI"],
                event_type="archive",
            ),
        ]
    )

    matches = storage.search_items(
        query="agent",
        source="OpenAI News",
        entity="Responses API",
        date_from="2026-03-29",
        date_to="2026-03-31",
        limit=10,
    )

    assert [match.item.url for match in matches] == [
        "https://openai.com/news/coding-agent-runtime/"
    ]
    assert matches[0].item.entities == ["OpenAI", "Responses API"]
    assert matches[0].item.event_type == "product-release"


def test_storage_search_migrates_legacy_database_before_query(tmp_path: Path) -> None:
    database_path = tmp_path / "digest.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE items (
                url TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_tier INTEGER NOT NULL,
                title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                excerpt TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO items (
                url, source_id, source_name, source_tier, title, published_at, excerpt
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://openai.com/news/agents/",
                "openai_news",
                "OpenAI News",
                0,
                "OpenAI agents update",
                datetime(2026, 4, 1, tzinfo=UTC).isoformat(),
                "Agent update",
            ),
        )

    storage = DigestStorage(database_path)

    matches = storage.search_items(query="agent", limit=5)

    assert [match.item.url for match in matches] == ["https://openai.com/news/agents/"]


def test_storage_lists_entity_timeline_newest_first(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    storage.upsert_items(
        [
            SourceItem(
                source_id="openai_news",
                source_name="OpenAI News",
                source_tier=0,
                title="OpenAI launches agent runtime",
                url="https://openai.com/news/agent-runtime/",
                published_at=datetime(2026, 4, 2, tzinfo=UTC),
                excerpt="Runtime update.",
                topics=["coding-agent"],
                entities=["OpenAI", "Responses API"],
                event_type="product-release",
            ),
            SourceItem(
                source_id="openai_news",
                source_name="OpenAI News",
                source_tier=0,
                title="OpenAI agent safety update",
                url="https://openai.com/news/agent-safety/",
                published_at=datetime(2026, 4, 1, tzinfo=UTC),
                excerpt="Safety update.",
                topics=["safety-governance"],
                entities=["OpenAI"],
                event_type="policy-update",
            ),
            SourceItem(
                source_id="anthropic_claude_blog",
                source_name="Anthropic Claude Blog",
                source_tier=0,
                title="Anthropic tool use update",
                url="https://anthropic.com/news/tool-use/",
                published_at=datetime(2026, 4, 3, tzinfo=UTC),
                excerpt="Tool use update.",
                topics=["tool-use"],
                entities=["Anthropic"],
                event_type="product-release",
            ),
        ]
    )

    matches = storage.list_entity_timeline(entity="OpenAI", limit=5)

    assert [match.item.url for match in matches] == [
        "https://openai.com/news/agent-runtime/",
        "https://openai.com/news/agent-safety/",
    ]
    assert matches[0].item.entities == ["OpenAI", "Responses API"]
    assert matches[0].item.event_type == "product-release"


def test_storage_searches_persisted_events_with_filters(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    primary = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI launches agent runtime",
        url="https://openai.com/news/agent-runtime/",
        published_at=datetime(2026, 4, 2, tzinfo=UTC),
        excerpt="Runtime update.",
        topics=["coding-agent"],
        entities=["OpenAI", "Responses API"],
        event_type="product-release",
        confidence=0.88,
        why_it_matters="This changes coding-agent deployment choices.",
    )
    secondary = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI agent safety update",
        url="https://openai.com/news/agent-safety/",
        published_at=datetime(2026, 4, 1, tzinfo=UTC),
        excerpt="Safety update.",
        topics=["safety-governance"],
        entities=["OpenAI"],
        event_type="policy-update",
    )
    storage.upsert_items([primary, secondary])
    run_id = storage.create_report_run(
        digest_date=datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
        pdf_path="output/2026-04-02.pdf",
        report_kind="daily",
        report_topic=None,
        tex_path="output/2026-04-02.tex",
    )
    storage.record_digest_entries(
        run_id,
        [
            (primary, "Primary summary", False),
            (secondary, "Secondary summary", False),
        ],
    )
    with sqlite3.connect(tmp_path / "digest.sqlite3") as connection:
        connection.execute("DELETE FROM digest_entries")

    events = storage.search_events(
        query="agent",
        event_type="product-release",
        entity="Responses API",
        limit=10,
    )

    assert [event.event_id for event in events] == ["https://openai.com/news/agent-runtime/"]
    assert events[0].summary == "Primary summary"
    assert events[0].entities == ["OpenAI", "Responses API"]
    assert events[0].confidence == 0.88
    assert events[0].why_it_matters == "This changes coding-agent deployment choices."


def test_storage_backfills_events_from_existing_digest_entries(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    item = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI launches agent runtime",
        url="https://openai.com/news/agent-runtime/",
        published_at=datetime(2026, 4, 2, tzinfo=UTC),
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
    with sqlite3.connect(tmp_path / "digest.sqlite3") as connection:
        connection.execute("DELETE FROM events")

    processed = storage.backfill_events()
    events = storage.search_events(query="agent", limit=10)

    assert processed == 1
    assert [event.event_id for event in events] == ["https://openai.com/news/agent-runtime/"]


def test_storage_search_events_supports_confidence_sort(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    stronger = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI launches agent runtime",
        url="https://openai.com/news/agent-runtime/",
        published_at=datetime(2026, 4, 2, tzinfo=UTC),
        excerpt="Runtime update.",
        topics=["coding-agent"],
        entities=["OpenAI"],
        event_type="product-release",
        confidence=0.95,
        why_it_matters="High-confidence update.",
    )
    weaker = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI agent safety update",
        url="https://openai.com/news/agent-safety/",
        published_at=datetime(2026, 4, 3, tzinfo=UTC),
        excerpt="Safety update.",
        topics=["safety-governance"],
        entities=["OpenAI"],
        event_type="policy-update",
        confidence=0.52,
        why_it_matters="Lower-confidence update.",
    )
    storage.upsert_items([stronger, weaker])
    run_id = storage.create_report_run(
        digest_date=datetime(2026, 4, 3, 10, 30, tzinfo=UTC),
        pdf_path="output/2026-04-03.pdf",
        report_kind="daily",
        report_topic=None,
        tex_path="output/2026-04-03.tex",
    )
    storage.record_digest_entries(
        run_id,
        [
            (stronger, "Stronger summary", False),
            (weaker, "Weaker summary", False),
        ],
    )

    events = storage.search_events(query="openai", sort_by="confidence", limit=10)

    assert [event.event_id for event in events] == [
        "https://openai.com/news/agent-runtime/",
        "https://openai.com/news/agent-safety/",
    ]


def test_storage_search_events_matches_natural_language_query_terms(tmp_path: Path) -> None:
    storage = DigestStorage(tmp_path / "digest.sqlite3")
    storage.initialize()
    item = SourceItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_tier=0,
        title="OpenAI launches agent runtime",
        url="https://openai.com/news/agent-runtime/",
        published_at=datetime(2026, 4, 2, tzinfo=UTC),
        excerpt="Runtime update.",
        topics=["coding-agent"],
        entities=["OpenAI"],
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

    events = storage.search_events(query="最近两周 OpenAI agent 相关变化", limit=10)

    assert [event.event_id for event in events] == ["https://openai.com/news/agent-runtime/"]
