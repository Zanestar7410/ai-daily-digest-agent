from __future__ import annotations

import json
from pathlib import Path

from ai_news_digest.models import DigestDocument, DigestDocumentEntry


def load_digest_document(path: Path) -> DigestDocument:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = [
        DigestDocumentEntry.model_validate(entry).to_digest_entry()
        for entry in raw["entries"]
    ]
    return DigestDocument.model_validate(
        {
            "digest_time": raw["digest_time"],
            "entries": entries,
        }
    )
