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
            ).with_timezone(),
            summary=self.summary,
            is_backfill=self.is_backfill,
        )


class DigestDocument(BaseModel):
    digest_time: datetime
    entries: list[DigestEntry]
