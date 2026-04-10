from datetime import UTC, datetime

from ai_news_digest.models import SourceItem
from ai_news_digest.selection import select_digest_items


def build_item(title: str, url: str, published_at: datetime, tier: int = 0) -> SourceItem:
    return SourceItem(
        source_id="source",
        source_name="Source",
        source_tier=tier,
        title=title,
        url=url,
        published_at=published_at,
        excerpt="Sample excerpt",
    )


def test_select_digest_items_prefers_recent_items_then_backfills() -> None:
    digest_time = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
    candidates = [
        build_item("Recent A", "https://example.com/a", datetime(2026, 4, 1, 8, 0, tzinfo=UTC)),
        build_item("Recent B", "https://example.com/b", datetime(2026, 3, 31, 12, 0, tzinfo=UTC)),
        build_item("Backfill C", "https://example.com/c", datetime(2026, 3, 24, 9, 0, tzinfo=UTC)),
        build_item("Too Old", "https://example.com/d", datetime(2026, 3, 10, 9, 0, tzinfo=UTC)),
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
        build_item("Recent A", "https://example.com/a", datetime(2026, 4, 1, 8, 0, tzinfo=UTC)),
        build_item("Recent B", "https://example.com/b", datetime(2026, 3, 31, 12, 0, tzinfo=UTC)),
        build_item("Backfill C", "https://example.com/c", datetime(2026, 3, 24, 9, 0, tzinfo=UTC)),
        build_item("Backfill D", "https://example.com/d", datetime(2026, 3, 23, 9, 0, tzinfo=UTC)),
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
