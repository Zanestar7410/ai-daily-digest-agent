from __future__ import annotations

from datetime import datetime, timedelta

from ai_news_digest.models import SelectedDigestItem, SourceItem


def _sort_key(item: SourceItem) -> tuple[int, float, str]:
    return (item.source_tier, -item.published_at.timestamp(), item.title)


def select_digest_items(
    candidates: list[SourceItem],
    digest_time: datetime,
    *,
    already_selected_urls: set[str] | None = None,
    min_items: int = 3,
    max_items: int = 5,
    freshness_window_days: int = 2,
    backfill_window_days: int = 14,
) -> list[SelectedDigestItem]:
    excluded = already_selected_urls or set()
    eligible = [item for item in candidates if item.url not in excluded]
    eligible.sort(key=_sort_key)

    freshness_cutoff = digest_time - timedelta(days=freshness_window_days)
    backfill_cutoff = digest_time - timedelta(days=backfill_window_days)

    recent = [item for item in eligible if item.published_at >= freshness_cutoff]
    selected = [SelectedDigestItem(item=item, is_backfill=False) for item in recent[:max_items]]

    if len(selected) >= min_items:
        return selected

    backfill_needed = min_items - len(selected)
    backfill_pool = [
        item
        for item in eligible
        if backfill_cutoff <= item.published_at < freshness_cutoff
    ]
    selected.extend(
        SelectedDigestItem(item=item, is_backfill=True)
        for item in backfill_pool[:backfill_needed]
    )
    return selected[:max_items]
