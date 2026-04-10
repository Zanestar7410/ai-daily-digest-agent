from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ai_news_digest.models import SourceItem


class DigestStorage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
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
                CREATE TABLE IF NOT EXISTS digest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest_date TEXT NOT NULL,
                    pdf_path TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS digest_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    item_url TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    is_backfill INTEGER NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES digest_runs(id)
                )
                """
            )

    def upsert_items(self, items: list[SourceItem]) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                """
                INSERT INTO items (
                    url, source_id, source_name, source_tier, title, published_at, excerpt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source_id = excluded.source_id,
                    source_name = excluded.source_name,
                    source_tier = excluded.source_tier,
                    title = excluded.title,
                    published_at = excluded.published_at,
                    excerpt = excluded.excerpt
                """,
                [
                    (
                        item.url,
                        item.source_id,
                        item.source_name,
                        item.source_tier,
                        item.title,
                        item.published_at.isoformat(),
                        item.excerpt,
                    )
                    for item in items
                ],
            )

    def list_unselected_items(self) -> list[SourceItem]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    items.source_id,
                    items.source_name,
                    items.source_tier,
                    items.title,
                    items.url,
                    items.published_at,
                    items.excerpt
                FROM items
                LEFT JOIN digest_entries ON digest_entries.item_url = items.url
                WHERE digest_entries.item_url IS NULL
                ORDER BY items.published_at DESC
                """
            ).fetchall()
        return [
            SourceItem(
                source_id=row[0],
                source_name=row[1],
                source_tier=row[2],
                title=row[3],
                url=row[4],
                published_at=datetime.fromisoformat(row[5]),
                excerpt=row[6],
            )
            for row in rows
        ]

    def create_digest_run(self, *, digest_date: datetime, pdf_path: str) -> int:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO digest_runs (digest_date, pdf_path) VALUES (?, ?)",
                (digest_date.isoformat(), pdf_path),
            )
            return int(cursor.lastrowid)

    def record_digest_entries(
        self,
        run_id: int,
        entries: list[tuple[SourceItem, str, bool]],
    ) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                """
                INSERT INTO digest_entries (run_id, item_url, summary, is_backfill)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (run_id, item.url, summary, int(is_backfill))
                    for item, summary, is_backfill in entries
                ],
            )
