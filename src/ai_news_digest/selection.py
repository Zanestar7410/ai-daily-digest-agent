from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

from ai_news_digest.models import SelectedDigestItem, SourceItem


EVENT_HOST_PREFIXES = ("event.",)
EVENT_PATH_MARKERS = (
    "/event/",
    "/events/",
    "/session/",
    "/agenda/",
    "/webinar/",
    "/conference/",
    "/summit/",
    "/register",
    "/tickets",
)


def _sort_key(item: SourceItem) -> tuple[int, float, str]:
    return (item.source_tier, -item.published_at.timestamp(), item.title)


def _is_event_or_program_page(item: SourceItem) -> bool:
    parsed = urlparse(item.url.lower())
    if any(parsed.netloc.startswith(prefix) for prefix in EVENT_HOST_PREFIXES):
        return True
    return any(marker in parsed.path for marker in EVENT_PATH_MARKERS)


def _take_items_with_source_limit(
    *,
    items: list[SourceItem],
    source_counts: dict[str, int],
    limit: int,
    max_per_source: int,
    is_backfill: bool,
) -> list[SelectedDigestItem]:
    selected: list[SelectedDigestItem] = []
    for item in items:
        if len(selected) >= limit:
            break
        if source_counts[item.source_id] >= max_per_source:
            continue
        source_counts[item.source_id] += 1
        selected.append(SelectedDigestItem(item=item, is_backfill=is_backfill))
    return selected


def select_digest_items(
    candidates: list[SourceItem],
    digest_time: datetime,
    *,
    already_selected_urls: set[str] | None = None,
    min_items: int = 3,
    max_items: int = 5,
    freshness_window_days: int = 2,
    backfill_window_days: int = 14,
    max_per_source: int = 2,
) -> list[SelectedDigestItem]:
    excluded = already_selected_urls or set()
    eligible = [
        item
        for item in candidates
        if item.url not in excluded
        and item.published_at <= digest_time
        and not _is_event_or_program_page(item)
    ]
    eligible.sort(key=_sort_key)

    freshness_cutoff = digest_time - timedelta(days=freshness_window_days)
    backfill_cutoff = digest_time - timedelta(days=backfill_window_days)

    recent = [item for item in eligible if item.published_at >= freshness_cutoff]
    source_counts: dict[str, int] = defaultdict(int)
    selected = _take_items_with_source_limit(
        items=recent,
        source_counts=source_counts,
        limit=max_items,
        max_per_source=max_per_source,
        is_backfill=False,
    )

    if len(selected) >= min_items:
        return selected

    backfill_needed = min_items - len(selected)
    backfill_pool = [
        item
        for item in eligible
        if backfill_cutoff <= item.published_at < freshness_cutoff
    ]
    selected.extend(
        _take_items_with_source_limit(
            items=backfill_pool,
            source_counts=source_counts,
            limit=backfill_needed,
            max_per_source=max_per_source,
            is_backfill=True,
        )
    )
    return selected[:max_items]
