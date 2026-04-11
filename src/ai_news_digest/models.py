from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


SourceKind = Literal["rss", "html"]


class SourceConfig(BaseModel):
    id: str
    name: str
    tier: int = Field(ge=0)
    kind: SourceKind
    entry_url: str
    adapter: str
    enabled: bool = True


class SearchSourceConfig(BaseModel):
    id: str
    name: str
    tier: int = Field(ge=0)
    domains: list[str]
    query_hint: str = ""
    enabled: bool = True


class SourceItem(BaseModel):
    source_id: str
    source_name: str
    source_tier: int = Field(ge=0)
    title: str
    url: str
    published_at: datetime
    excerpt: str = ""
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    event_type: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    why_it_matters: str = ""

    def with_timezone(self) -> "SourceItem":
        if self.published_at.tzinfo is None:
            return self.model_copy(update={"published_at": self.published_at.replace(tzinfo=UTC)})
        return self


class SelectedDigestItem(BaseModel):
    item: SourceItem
    is_backfill: bool = False


class DigestEntry(BaseModel):
    item: SourceItem
    summary: str
    is_backfill: bool = False


class DigestDocumentEntry(BaseModel):
    source_id: str
    source_name: str
    source_tier: int = Field(ge=0)
    title: str
    url: str
    published_at: datetime
    summary: str
    is_backfill: bool = False
    excerpt: str = ""
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    event_type: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    why_it_matters: str = ""

    def to_digest_entry(self) -> DigestEntry:
        return DigestEntry(
            item=SourceItem(
                source_id=self.source_id,
                source_name=self.source_name,
                source_tier=self.source_tier,
                title=self.title,
                url=self.url,
                published_at=self.published_at,
                excerpt=self.excerpt,
                topics=self.topics,
                entities=self.entities,
                event_type=self.event_type,
                confidence=self.confidence,
                why_it_matters=self.why_it_matters,
            ).with_timezone(),
            summary=self.summary,
            is_backfill=self.is_backfill,
        )


class DigestDocument(BaseModel):
    digest_time: datetime
    entries: list[DigestEntry]


class HistoricalSearchMatch(BaseModel):
    item: SourceItem
    summary: str | None = None
    report_date: datetime | None = None
    report_kind: str | None = None
    report_topic: str | None = None
    report_path: str | None = None


class EventRecord(BaseModel):
    event_id: str
    title: str
    summary: str
    event_type: str = ""
    source_name: str
    source_tier: int = Field(ge=0)
    published_at: datetime
    url: str
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    excerpt: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    why_it_matters: str = ""
