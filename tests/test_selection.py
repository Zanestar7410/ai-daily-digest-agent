from datetime import UTC, datetime

from ai_news_digest.models import SourceItem
from ai_news_digest.selection import select_digest_items


def build_item(
    title: str,
    url: str,
    published_at: datetime,
    tier: int = 0,
    source_id: str = "source",
    source_name: str = "Source",
) -> SourceItem:
    return SourceItem(
        source_id=source_id,
        source_name=source_name,
        source_tier=tier,
        title=title,
        url=url,
        published_at=published_at,
        excerpt="Sample excerpt",
    )


def test_select_digest_items_prefers_recent_items_then_backfills() -> None:
    digest_time = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
    candidates = [
        build_item("Recent A", "https://example.com/a", datetime(2026, 4, 1, 8, 0, tzinfo=UTC), source_id="a"),
        build_item("Recent B", "https://example.com/b", datetime(2026, 3, 31, 12, 0, tzinfo=UTC), source_id="b"),
        build_item("Backfill C", "https://example.com/c", datetime(2026, 3, 24, 9, 0, tzinfo=UTC), source_id="c"),
        build_item("Too Old", "https://example.com/d", datetime(2026, 3, 10, 9, 0, tzinfo=UTC), source_id="d"),
    ]

    selected = select_digest_items(
        candidates=candidates,
        digest_time=digest_time,
        min_items=3,
        max_items=5,
        freshness_window_days=2,
        backfill_window_days=14,
    )

    assert [item.item.title for item in selected] == ["Recent A", "Recent B", "Backfill C"]
    assert [item.is_backfill for item in selected] == [False, False, True]


def test_select_digest_items_excludes_already_selected_urls() -> None:
    digest_time = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
    candidates = [
        build_item("Recent A", "https://example.com/a", datetime(2026, 4, 1, 8, 0, tzinfo=UTC), source_id="a"),
        build_item("Recent B", "https://example.com/b", datetime(2026, 3, 31, 12, 0, tzinfo=UTC), source_id="b"),
        build_item("Backfill C", "https://example.com/c", datetime(2026, 3, 24, 9, 0, tzinfo=UTC), source_id="c"),
        build_item("Backfill D", "https://example.com/d", datetime(2026, 3, 23, 9, 0, tzinfo=UTC), source_id="d"),
    ]

    selected = select_digest_items(
        candidates=candidates,
        digest_time=digest_time,
        already_selected_urls={"https://example.com/c"},
        min_items=3,
        max_items=5,
        freshness_window_days=2,
        backfill_window_days=14,
    )

    assert [item.item.title for item in selected] == ["Recent A", "Recent B", "Backfill D"]


def test_select_digest_items_excludes_future_items_and_event_pages() -> None:
    digest_time = datetime(2026, 4, 10, 10, 30, tzinfo=UTC)
    candidates = [
        build_item(
            "Future event page",
            "https://event.technologyreview.com/emtech-ai-2026/session/3067731/reskilling-the-frontline-for-the-ai-era",
            datetime(2026, 4, 23, 9, 0, tzinfo=UTC),
            tier=2,
            source_id="mit_technology_review_ai",
            source_name="MIT Technology Review AI",
        ),
        build_item(
            "Current event page",
            "https://event.technologyreview.com/emtech-ai-2026/session/3067737/from-messaging-to-conversion-with-ai",
            datetime(2026, 4, 9, 9, 0, tzinfo=UTC),
            tier=2,
            source_id="mit_technology_review_ai",
            source_name="MIT Technology Review AI",
        ),
        build_item(
            "Official launch",
            "https://openai.com/index/product-update/",
            datetime(2026, 4, 9, 8, 0, tzinfo=UTC),
            tier=0,
            source_id="openai_news",
            source_name="OpenAI News",
        ),
        build_item(
            "Policy note",
            "https://www.anthropic.com/news/policy-note",
            datetime(2026, 4, 8, 8, 0, tzinfo=UTC),
            tier=0,
            source_id="anthropic_news",
            source_name="Anthropic News",
        ),
    ]

    selected = select_digest_items(candidates=candidates, digest_time=digest_time, max_items=5)

    assert [item.item.title for item in selected] == ["Official launch", "Policy note"]


def test_select_digest_items_limits_items_per_source() -> None:
    digest_time = datetime(2026, 4, 10, 10, 30, tzinfo=UTC)
    candidates = [
        build_item(
            "OpenAI A",
            "https://openai.com/index/a/",
            datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
            tier=0,
            source_id="openai_news",
            source_name="OpenAI News",
        ),
        build_item(
            "OpenAI B",
            "https://openai.com/index/b/",
            datetime(2026, 4, 10, 8, 0, tzinfo=UTC),
            tier=0,
            source_id="openai_news",
            source_name="OpenAI News",
        ),
        build_item(
            "OpenAI C",
            "https://openai.com/index/c/",
            datetime(2026, 4, 10, 7, 0, tzinfo=UTC),
            tier=0,
            source_id="openai_news",
            source_name="OpenAI News",
        ),
        build_item(
            "Anthropic A",
            "https://www.anthropic.com/news/a/",
            datetime(2026, 4, 10, 6, 0, tzinfo=UTC),
            tier=0,
            source_id="anthropic_news",
            source_name="Anthropic News",
        ),
    ]

    selected = select_digest_items(candidates=candidates, digest_time=digest_time, max_items=5)

    assert [item.item.title for item in selected] == ["OpenAI A", "OpenAI B", "Anthropic A"]
