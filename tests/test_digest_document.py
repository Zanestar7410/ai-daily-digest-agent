from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.digest_document import load_digest_document


def test_load_digest_document_from_json(tmp_path: Path) -> None:
    payload = """\
{
  "digest_time": "2026-04-05T10:30:00+02:00",
  "entries": [
    {
      "source_id": "openai_news",
      "source_name": "OpenAI News",
      "source_tier": 0,
      "title": "OpenAI updates safety guidance",
      "url": "https://openai.com/news/safety-guidance/",
      "published_at": "2026-04-04T09:00:00+00:00",
      "summary": "中文摘要一",
      "is_backfill": false
    }
  ]
}
"""
    path = tmp_path / "digest.json"
    path.write_text(payload, encoding="utf-8")

    document = load_digest_document(path)

    assert document.digest_time == datetime(2026, 4, 5, 10, 30, tzinfo=datetime.fromisoformat("2026-04-05T10:30:00+02:00").tzinfo)
    assert len(document.entries) == 1
    assert document.entries[0].summary == "中文摘要一"
    assert document.entries[0].item.published_at == datetime(2026, 4, 4, 9, 0, tzinfo=UTC)
