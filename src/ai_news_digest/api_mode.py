from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ai_news_digest.models import DigestDocument, DigestDocumentEntry, SearchSourceConfig, SourceItem
from ai_news_digest.selection import select_digest_items
from ai_news_digest.storage import DigestStorage

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class SearchResultEntry(BaseModel):
    title: str
    url: str
    published_at: datetime
    excerpt: str = ""


class SearchBatch(BaseModel):
    entries: list[SearchResultEntry]


class SummaryEntry(BaseModel):
    url: str
    summary: str


class BatchSummary(BaseModel):
    entries: list[SummaryEntry]


class OpenAIWebSearchCollector:
    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        model: str = "gpt-5.4",
        reasoning_effort: str = "medium",
        search_context_size: str = "high",
    ) -> None:
        if client is not None:
            self.client = client
        elif OpenAI is not None:
            self.client = OpenAI()
        else:  # pragma: no cover
            raise RuntimeError("Install the 'api' extra to enable OpenAI API mode.")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.search_context_size = search_context_size

    def collect_items(
        self,
        *,
        sources: list[SearchSourceConfig],
        digest_time: datetime,
        lookback_days: int = 14,
    ) -> list[SourceItem]:
        items: list[SourceItem] = []
        seen_urls: set[str] = set()

        for source in sources:
            response = self.client.responses.parse(
                model=self.model,
                reasoning={"effort": self.reasoning_effort},
                tools=[
                    {
                        "type": "web_search",
                        "filters": {"allowed_domains": source.domains},
                        "search_context_size": self.search_context_size,
                    }
                ],
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Search the web and return only authoritative English-language AI updates "
                            "from the allowed domains. Prefer official first-party sources, then "
                            "authoritative institutions, then high-quality media, then high-signal "
                            "GitHub community posts. Return structured results only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": "\n".join(
                            [
                                f"Digest time: {digest_time.isoformat()}",
                                f"Lookback window: {lookback_days} days",
                                f"Source label: {source.name}",
                                f"Allowed domains: {', '.join(source.domains)}",
                                f"Search focus: {source.query_hint}",
                                "Find recent AI-related updates and return up to 5 items.",
                                "Each item must include title, canonical URL, publication timestamp, and a short English excerpt.",
                            ]
                        ),
                    },
                ],
                text_format=SearchBatch,
            )
            parsed: SearchBatch = response.output_parsed
            for entry in parsed.entries:
                if entry.url in seen_urls:
                    continue
                seen_urls.add(entry.url)
                items.append(
                    SourceItem(
                        source_id=source.id,
                        source_name=source.name,
                        source_tier=source.tier,
                        title=entry.title,
                        url=entry.url,
                        published_at=entry.published_at,
                        excerpt=entry.excerpt,
                    ).with_timezone()
                )
        return items


class OpenAISummarizer:
    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        model: str = "gpt-5.4",
        reasoning_effort: str = "medium",
    ) -> None:
        if client is not None:
            self.client = client
        elif OpenAI is not None:
            self.client = OpenAI()
        else:  # pragma: no cover
            raise RuntimeError("Install the 'api' extra to enable OpenAI API mode.")
        self.model = model
        self.reasoning_effort = reasoning_effort

    def summarize_items(self, items: list[SourceItem]) -> dict[str, str]:
        if not items:
            return {}

        response = self.client.responses.parse(
            model=self.model,
            reasoning={"effort": self.reasoning_effort},
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write concise Chinese summaries for an AI daily digest. "
                        "Be factual and specific. Do not use hype."
                    ),
                },
                {
                    "role": "user",
                    "content": "\n\n".join(
                        "\n".join(
                            [
                                f"Title: {item.title}",
                                f"Source: {item.source_name}",
                                f"URL: {item.url}",
                                f"Published: {item.published_at.isoformat()}",
                                f"Excerpt: {item.excerpt}",
                            ]
                        )
                        for item in items
                    ),
                },
            ],
            text_format=BatchSummary,
        )
        parsed: BatchSummary = response.output_parsed
        summary_map = {entry.url: entry.summary for entry in parsed.entries}
        missing = [item.url for item in items if item.url not in summary_map]
        if missing:
            raise ValueError(f"Missing summaries for URLs: {', '.join(missing)}")
        return summary_map


def build_api_digest_document(
    *,
    sources: list[SearchSourceConfig],
    collector: OpenAIWebSearchCollector,
    summarizer: OpenAISummarizer,
    storage: DigestStorage,
    digest_time: datetime,
    dry_run: bool = False,
    json_output_path: Path | None = None,
) -> DigestDocument:
    fetched_items = collector.collect_items(sources=sources, digest_time=digest_time)
    selected_urls = storage.list_selected_urls()
    selected = select_digest_items(
        candidates=fetched_items,
        digest_time=digest_time,
        already_selected_urls=selected_urls,
    )

    if not dry_run:
        storage.initialize()
        storage.upsert_items(fetched_items)

    summary_map = summarizer.summarize_items([item.item for item in selected])

    entries = [
        DigestDocumentEntry(
            source_id=selected_item.item.source_id,
            source_name=selected_item.item.source_name,
            source_tier=selected_item.item.source_tier,
            title=selected_item.item.title,
            url=selected_item.item.url,
            published_at=selected_item.item.published_at,
            summary=summary_map[selected_item.item.url],
            is_backfill=selected_item.is_backfill,
            excerpt=selected_item.item.excerpt,
        ).to_digest_entry()
        for selected_item in selected
    ]

    document = DigestDocument(digest_time=digest_time, entries=entries)
    if json_output_path is not None:
        save_digest_document(document=document, path=json_output_path)
    return document


def save_digest_document(*, document: DigestDocument, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "digest_time": document.digest_time.isoformat(),
        "entries": [
            {
                "source_id": entry.item.source_id,
                "source_name": entry.item.source_name,
                "source_tier": entry.item.source_tier,
                "title": entry.item.title,
                "url": entry.item.url,
                "published_at": entry.item.published_at.isoformat(),
                "summary": entry.summary,
                "is_backfill": entry.is_backfill,
                "excerpt": entry.item.excerpt,
            }
            for entry in document.entries
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
