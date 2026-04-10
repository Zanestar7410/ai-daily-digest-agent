from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.models import SourceItem
from ai_news_digest.storage import DigestStorage


def build_item(url: str, published_at: datetime) -> SourceItem:
    return SourceItem(
        source_id="google_ai_blog",
        source_name="Google AI Blog",
        source_tier=0,
        title=url.rsplit("/", maxsplit=1)[-1],
        url=url,
        published_at=published_at,
        excerpt="Sample excerpt",
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
