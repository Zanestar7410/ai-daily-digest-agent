from __future__ import annotations

import json
from pathlib import Path

from ai_news_digest.models import SearchSourceConfig, SourceConfig


def load_source_registry(path: Path) -> list[SourceConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SourceConfig.model_validate(item) for item in raw if item.get("enabled", True)]


def load_search_registry(path: Path) -> list[SearchSourceConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SearchSourceConfig.model_validate(item) for item in raw if item.get("enabled", True)]
