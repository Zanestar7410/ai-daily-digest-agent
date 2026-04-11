from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from ai_news_digest.models import EventRecord, HistoricalSearchMatch, SourceItem


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


QUERY_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*|[\u4e00-\u9fff]{2,}")


def _build_text_search_clause(columns: list[str], query: str) -> tuple[str, list[str]]:
    raw_terms = [query.strip().lower(), *[term.lower() for term in QUERY_TOKEN_RE.findall(query)]]
    seen: set[str] = set()
    terms: list[str] = []
    for term in raw_terms:
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)

    if not terms:
        return "1=1", []

    comparisons: list[str] = []
    params: list[str] = []
    for term in terms:
        comparisons.append("(" + " OR ".join(f"LOWER({column}) LIKE ?" for column in columns) + ")")
        params.extend([f"%{term}%"] * len(columns))
    return "(" + " OR ".join(comparisons) + ")", params


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


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
                    excerpt TEXT NOT NULL,
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    entities_json TEXT NOT NULL DEFAULT '[]',
                    event_type TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0,
                    why_it_matters TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS digest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest_date TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    report_kind TEXT NOT NULL DEFAULT 'daily',
                    report_topic TEXT,
                    tex_path TEXT NOT NULL DEFAULT '',
                    json_path TEXT
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    item_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT '',
                    source_name TEXT NOT NULL,
                    source_tier INTEGER NOT NULL,
                    published_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    entities_json TEXT NOT NULL DEFAULT '[]',
                    excerpt TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    why_it_matters TEXT NOT NULL DEFAULT '',
                    report_date TEXT NOT NULL,
                    report_kind TEXT NOT NULL DEFAULT 'daily',
                    report_topic TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    output_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ensure_column(
                connection,
                "items",
                "topics_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            _ensure_column(
                connection,
                "items",
                "entities_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            _ensure_column(
                connection,
                "items",
                "event_type",
                "TEXT NOT NULL DEFAULT ''",
            )
            _ensure_column(connection, "items", "confidence", "REAL NOT NULL DEFAULT 0")
            _ensure_column(connection, "items", "why_it_matters", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(
                connection,
                "digest_runs",
                "report_kind",
                "TEXT NOT NULL DEFAULT 'daily'",
            )
            _ensure_column(connection, "digest_runs", "report_topic", "TEXT")
            _ensure_column(
                connection,
                "digest_runs",
                "tex_path",
                "TEXT NOT NULL DEFAULT ''",
            )
            _ensure_column(connection, "digest_runs", "json_path", "TEXT")
            _ensure_column(connection, "events", "item_url", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "title", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "summary", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "event_type", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "source_name", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "source_tier", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(connection, "events", "published_at", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "url", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "topics_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(connection, "events", "entities_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(connection, "events", "excerpt", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "confidence", "REAL NOT NULL DEFAULT 0")
            _ensure_column(connection, "events", "why_it_matters", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "report_date", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "events", "report_kind", "TEXT NOT NULL DEFAULT 'daily'")
            _ensure_column(connection, "events", "report_topic", "TEXT")
            _ensure_column(connection, "research_reports", "query", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "research_reports", "generated_at", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "research_reports", "markdown", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "research_reports", "report_json", "TEXT NOT NULL DEFAULT '{}'")
            _ensure_column(connection, "research_reports", "output_path", "TEXT")
            _ensure_column(connection, "research_reports", "created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")

    def upsert_items(self, items: list[SourceItem]) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                """
                INSERT INTO items (
                    url, source_id, source_name, source_tier, title, published_at, excerpt, topics_json, entities_json, event_type, confidence, why_it_matters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source_id = excluded.source_id,
                    source_name = excluded.source_name,
                    source_tier = excluded.source_tier,
                    title = excluded.title,
                    published_at = excluded.published_at,
                    excerpt = excluded.excerpt,
                    topics_json = CASE
                        WHEN excluded.topics_json = '[]' THEN items.topics_json
                        ELSE excluded.topics_json
                    END,
                    entities_json = CASE
                        WHEN excluded.entities_json = '[]' THEN items.entities_json
                        ELSE excluded.entities_json
                    END,
                    event_type = CASE
                        WHEN excluded.event_type = '' THEN items.event_type
                        ELSE excluded.event_type
                    END,
                    confidence = CASE
                        WHEN excluded.confidence = 0 THEN items.confidence
                        ELSE excluded.confidence
                    END,
                    why_it_matters = CASE
                        WHEN excluded.why_it_matters = '' THEN items.why_it_matters
                        ELSE excluded.why_it_matters
                    END
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
                        json.dumps(item.topics, ensure_ascii=False),
                        json.dumps(item.entities, ensure_ascii=False),
                        item.event_type,
                        item.confidence,
                        item.why_it_matters,
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
                    items.excerpt,
                    items.topics_json,
                    items.entities_json,
                    items.event_type,
                    items.confidence,
                    items.why_it_matters
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
                topics=json.loads(row[7]),
                entities=json.loads(row[8]),
                event_type=row[9],
                confidence=row[10],
                why_it_matters=row[11],
            )
            for row in rows
        ]

    def list_selected_urls(self) -> set[str]:
        if not self.database_path.exists():
            return set()

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT DISTINCT item_url FROM digest_entries"
            ).fetchall()
        return {row[0] for row in rows}

    def create_digest_run(self, *, digest_date: datetime, pdf_path: str) -> int:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO digest_runs (
                    digest_date, pdf_path, report_kind, report_topic, tex_path, json_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest_date.isoformat(),
                    pdf_path,
                    "daily",
                    None,
                    "",
                    None,
                ),
            )
            return int(cursor.lastrowid)

    def create_report_run(
        self,
        *,
        digest_date: datetime,
        pdf_path: str,
        report_kind: str,
        report_topic: str | None,
        tex_path: str,
        json_path: str | None = None,
    ) -> int:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO digest_runs (
                    digest_date, pdf_path, report_kind, report_topic, tex_path, json_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest_date.isoformat(),
                    pdf_path,
                    report_kind,
                    report_topic,
                    tex_path,
                    json_path,
                ),
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
            run_metadata = connection.execute(
                """
                SELECT digest_date, report_kind, report_topic
                FROM digest_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if run_metadata is None:
                raise ValueError(f"Unknown digest run id: {run_id}")
            digest_date, report_kind, report_topic = run_metadata
            connection.executemany(
                """
                INSERT INTO events (
                    event_id,
                    item_url,
                    title,
                    summary,
                    event_type,
                    source_name,
                    source_tier,
                    published_at,
                    url,
                    topics_json,
                    entities_json,
                    excerpt,
                    confidence,
                    why_it_matters,
                    report_date,
                    report_kind,
                    report_topic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    item_url = excluded.item_url,
                    title = excluded.title,
                    summary = excluded.summary,
                    event_type = excluded.event_type,
                    source_name = excluded.source_name,
                    source_tier = excluded.source_tier,
                    published_at = excluded.published_at,
                    url = excluded.url,
                    topics_json = excluded.topics_json,
                    entities_json = excluded.entities_json,
                    excerpt = excluded.excerpt,
                    confidence = excluded.confidence,
                    why_it_matters = excluded.why_it_matters,
                    report_date = excluded.report_date,
                    report_kind = excluded.report_kind,
                    report_topic = excluded.report_topic
                """,
                [
                    (
                        item.url,
                        item.url,
                        item.title,
                        summary,
                        item.event_type,
                        item.source_name,
                        item.source_tier,
                        item.published_at.isoformat(),
                        item.url,
                        json.dumps(item.topics, ensure_ascii=False),
                        json.dumps(item.entities, ensure_ascii=False),
                        item.excerpt,
                        item.confidence,
                        item.why_it_matters,
                        digest_date,
                        report_kind,
                        report_topic,
                    )
                    for item, summary, _ in entries
                ],
            )

    def search_items(
        self,
        *,
        query: str,
        topic: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
    ) -> list[HistoricalSearchMatch]:
        if not self.database_path.exists():
            return []

        self.initialize()
        topic_like = f'%"{topic.lower()}"%' if topic is not None else None
        entity_like = f'%"{entity.lower()}"%' if entity is not None else None
        search_clause, search_params = _build_text_search_clause(
            [
                "items.title",
                "items.excerpt",
                "items.source_name",
                "items.url",
                """
                COALESCE(
                    (
                        SELECT de.summary
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ),
                    ''
                )
                """.strip(),
            ],
            query,
        )
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    items.source_id,
                    items.source_name,
                    items.source_tier,
                    items.title,
                    items.url,
                    items.published_at,
                    items.excerpt,
                    items.topics_json,
                    items.entities_json,
                    items.event_type,
                    items.confidence,
                    items.why_it_matters,
                    (
                        SELECT de.summary
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ) AS summary,
                    (
                        SELECT dr.digest_date
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ) AS digest_date,
                    (
                        SELECT dr.report_kind
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ) AS report_kind,
                    (
                        SELECT dr.report_topic
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ) AS report_topic,
                    (
                        SELECT dr.pdf_path
                        FROM digest_entries AS de
                        JOIN digest_runs AS dr ON dr.id = de.run_id
                        WHERE de.item_url = items.url
                        ORDER BY dr.digest_date DESC, dr.id DESC
                        LIMIT 1
                    ) AS report_path
                FROM items
                WHERE {search_clause}
                AND (? IS NULL OR LOWER(items.topics_json) LIKE ?)
                AND (? IS NULL OR LOWER(items.source_name) = LOWER(?))
                AND (? IS NULL OR LOWER(items.entities_json) LIKE ?)
                AND (? IS NULL OR DATE(items.published_at) >= DATE(?))
                AND (? IS NULL OR DATE(items.published_at) <= DATE(?))
                ORDER BY items.published_at DESC
                LIMIT ?
                """,
                (
                    *search_params,
                    topic,
                    topic_like,
                    source,
                    source,
                    entity,
                    entity_like,
                    date_from,
                    date_from,
                    date_to,
                    date_to,
                    limit,
                ),
            ).fetchall()

        matches: list[HistoricalSearchMatch] = []
        for row in rows:
            report_date = datetime.fromisoformat(row[13]) if row[13] else None
            matches.append(
                HistoricalSearchMatch(
                    item=SourceItem(
                        source_id=row[0],
                        source_name=row[1],
                        source_tier=row[2],
                        title=row[3],
                        url=row[4],
                        published_at=datetime.fromisoformat(row[5]),
                        excerpt=row[6],
                        topics=json.loads(row[7]),
                        entities=json.loads(row[8]),
                        event_type=row[9],
                        confidence=row[10],
                        why_it_matters=row[11],
                    ),
                    summary=row[12],
                    report_date=report_date,
                    report_kind=row[14],
                    report_topic=row[15],
                    report_path=row[16],
                )
            )
        return matches

    def list_entity_timeline(
        self,
        *,
        entity: str,
        limit: int = 20,
    ) -> list[HistoricalSearchMatch]:
        if not self.database_path.exists():
            return []

        self.initialize()
        entity_like = f'%"{entity.lower()}"%'
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
                    items.excerpt,
                    items.topics_json,
                    items.entities_json,
                    items.event_type,
                    items.confidence,
                    items.why_it_matters
                FROM items
                WHERE LOWER(items.entities_json) LIKE ?
                ORDER BY items.published_at DESC
                LIMIT ?
                """,
                (entity_like, limit),
            ).fetchall()

        return [
            HistoricalSearchMatch(
                item=SourceItem(
                    source_id=row[0],
                    source_name=row[1],
                    source_tier=row[2],
                    title=row[3],
                    url=row[4],
                    published_at=datetime.fromisoformat(row[5]),
                    excerpt=row[6],
                    topics=json.loads(row[7]),
                    entities=json.loads(row[8]),
                    event_type=row[9],
                    confidence=row[10],
                    why_it_matters=row[11],
                )
            )
            for row in rows
        ]

    def search_events(
        self,
        *,
        query: str,
        topic: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "published_at",
        limit: int = 20,
    ) -> list[EventRecord]:
        if not self.database_path.exists():
            return []

        self.initialize()
        topic_like = f'%"{topic.lower()}"%' if topic is not None else None
        entity_like = f'%"{entity.lower()}"%' if entity is not None else None
        search_clause, search_params = _build_text_search_clause(
            [
                "events.title",
                "events.excerpt",
                "events.source_name",
                "events.url",
                "events.summary",
            ],
            query,
        )
        order_clause = {
            "published_at": "events.published_at DESC, events.event_id ASC",
            "confidence": "events.confidence DESC, events.published_at DESC, events.event_id ASC",
        }.get(sort_by, "events.published_at DESC, events.event_id ASC")
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    events.title,
                    events.url,
                    events.published_at,
                    events.excerpt,
                    events.topics_json,
                    events.entities_json,
                    events.event_type,
                    events.confidence,
                    events.why_it_matters,
                    events.source_name,
                    events.source_tier,
                    events.summary,
                    events.event_id
                FROM events
                WHERE {search_clause}
                AND (? IS NULL OR LOWER(events.topics_json) LIKE ?)
                AND (? IS NULL OR LOWER(events.source_name) = LOWER(?))
                AND (? IS NULL OR LOWER(events.entities_json) LIKE ?)
                AND (? IS NULL OR LOWER(events.event_type) = LOWER(?))
                AND (? IS NULL OR DATE(events.published_at) >= DATE(?))
                AND (? IS NULL OR DATE(events.published_at) <= DATE(?))
                ORDER BY {order_clause}
                LIMIT ?
                """,
                (
                    *search_params,
                    topic,
                    topic_like,
                    source,
                    source,
                    entity,
                    entity_like,
                    event_type,
                    event_type,
                    date_from,
                    date_from,
                    date_to,
                    date_to,
                    limit,
                ),
            ).fetchall()

        return [
            EventRecord(
                event_id=row[12],
                title=row[0],
                summary=row[11],
                event_type=row[6],
                source_name=row[9],
                source_tier=row[10],
                published_at=datetime.fromisoformat(row[2]),
                url=row[1],
                topics=json.loads(row[4]),
                entities=json.loads(row[5]),
                excerpt=row[3],
                confidence=row[7],
                why_it_matters=row[8],
            )
            for row in rows
        ]

    def backfill_events(self) -> int:
        if not self.database_path.exists():
            return 0

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    items.url,
                    items.title,
                    items.source_name,
                    items.source_tier,
                    items.published_at,
                    items.excerpt,
                    items.topics_json,
                    items.entities_json,
                    items.event_type,
                    items.confidence,
                    items.why_it_matters,
                    de.summary,
                    dr.digest_date,
                    dr.report_kind,
                    dr.report_topic
                FROM digest_entries AS de
                JOIN digest_runs AS dr ON dr.id = de.run_id
                JOIN items ON items.url = de.item_url
                ORDER BY dr.digest_date ASC, dr.id ASC
                """
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO events (
                    event_id,
                    item_url,
                    title,
                    summary,
                    event_type,
                    source_name,
                    source_tier,
                    published_at,
                    url,
                    topics_json,
                    entities_json,
                    excerpt,
                    confidence,
                    why_it_matters,
                    report_date,
                    report_kind,
                    report_topic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    item_url = excluded.item_url,
                    title = excluded.title,
                    summary = excluded.summary,
                    event_type = excluded.event_type,
                    source_name = excluded.source_name,
                    source_tier = excluded.source_tier,
                    published_at = excluded.published_at,
                    url = excluded.url,
                    topics_json = excluded.topics_json,
                    entities_json = excluded.entities_json,
                    excerpt = excluded.excerpt,
                    confidence = excluded.confidence,
                    why_it_matters = excluded.why_it_matters,
                    report_date = excluded.report_date,
                    report_kind = excluded.report_kind,
                    report_topic = excluded.report_topic
                """,
                [
                    (
                        row[0],
                        row[0],
                        row[1],
                        row[11],
                        row[8],
                        row[2],
                        row[3],
                        row[4],
                        row[0],
                        row[6],
                        row[7],
                        row[5],
                        row[9],
                        row[10],
                        row[12],
                        row[13],
                        row[14],
                    )
                    for row in rows
                ],
            )
        return len(rows)

    def list_entities(self, *, limit: int = 20) -> list[dict[str, object]]:
        if not self.database_path.exists():
            return []

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    json_each.value AS name,
                    COUNT(*) AS mention_count,
                    MAX(events.published_at) AS latest_published_at
                FROM events, json_each(events.entities_json)
                GROUP BY json_each.value
                ORDER BY mention_count DESC, latest_published_at DESC, name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "name": row[0],
                "count": row[1],
                "latest_published_at": row[2],
            }
            for row in rows
        ]

    def list_topics(self, *, limit: int = 20) -> list[dict[str, object]]:
        if not self.database_path.exists():
            return []

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    json_each.value AS name,
                    COUNT(*) AS mention_count,
                    MAX(events.published_at) AS latest_published_at
                FROM events, json_each(events.topics_json)
                GROUP BY json_each.value
                ORDER BY mention_count DESC, latest_published_at DESC, name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "name": row[0],
                "count": row[1],
                "latest_published_at": row[2],
            }
            for row in rows
        ]

    def save_research_report(
        self,
        *,
        report: object,
        markdown: str,
        output_path: str | None = None,
    ) -> int:
        self.initialize()
        if hasattr(report, "model_dump"):
            payload = report.model_dump(mode="json")  # type: ignore[assignment]
        elif isinstance(report, dict):
            payload = report
        else:
            raise TypeError("report must be a pydantic model or dict")
        generated_at = payload["generated_at"]
        if isinstance(generated_at, datetime):
            generated_at_value = generated_at.isoformat()
        else:
            generated_at_value = str(generated_at)

        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO research_reports (
                    query, generated_at, markdown, report_json, output_path
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["query"],
                    generated_at_value,
                    markdown,
                    json.dumps(payload, ensure_ascii=False, default=_json_default),
                    output_path,
                ),
            )
            return int(cursor.lastrowid)

    def list_research_reports(self, *, limit: int = 20) -> list[dict[str, object]]:
        if not self.database_path.exists():
            return []

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, query, generated_at, output_path, created_at
                FROM research_reports
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "query": row[1],
                "generated_at": row[2],
                "output_path": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    def get_research_report(self, *, report_id: int) -> dict[str, object] | None:
        if not self.database_path.exists():
            return None

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, query, generated_at, markdown, report_json, output_path, created_at
                FROM research_reports
                WHERE id = ?
                """,
                (report_id,),
            ).fetchone()

        if row is None:
            return None

        payload = json.loads(row[4])
        payload.update(
            {
                "id": row[0],
                "query": row[1],
                "generated_at": row[2],
                "markdown": row[3],
                "output_path": row[5],
                "created_at": row[6],
            }
        )
        return payload

    def get_event(self, *, event_id: str) -> EventRecord | None:
        if not self.database_path.exists():
            return None

        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    events.title,
                    events.url,
                    events.published_at,
                    events.excerpt,
                    events.topics_json,
                    events.entities_json,
                    events.event_type,
                    events.confidence,
                    events.why_it_matters,
                    events.source_name,
                    events.source_tier,
                    events.summary,
                    events.event_id
                FROM events
                WHERE events.event_id = ?
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            return None

        return EventRecord(
            event_id=row[12],
            title=row[0],
            summary=row[11],
            event_type=row[6],
            source_name=row[9],
            source_tier=row[10],
            published_at=datetime.fromisoformat(row[2]),
            url=row[1],
            topics=json.loads(row[4]),
            entities=json.loads(row[5]),
            excerpt=row[3],
            confidence=row[7],
            why_it_matters=row[8],
        )
