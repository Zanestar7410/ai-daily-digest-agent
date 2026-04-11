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
      "summary": "Chinese summary placeholder.",
      "is_backfill": false,
      "topics": ["safety-governance"],
      "entities": ["OpenAI"],
      "event_type": "policy-update",
      "confidence": 0.91,
      "why_it_matters": "This affects enterprise rollout decisions."
    }
  ]
}
"""
    path = tmp_path / "digest.json"
    path.write_text(payload, encoding="utf-8")

    document = load_digest_document(path)

    expected_tz = datetime.fromisoformat("2026-04-05T10:30:00+02:00").tzinfo
    assert document.digest_time == datetime(2026, 4, 5, 10, 30, tzinfo=expected_tz)
    assert len(document.entries) == 1
    assert document.entries[0].summary == "Chinese summary placeholder."
    assert document.entries[0].item.published_at == datetime(2026, 4, 4, 9, 0, tzinfo=UTC)
    assert document.entries[0].item.topics == ["safety-governance"]
    assert document.entries[0].item.entities == ["OpenAI"]
    assert document.entries[0].item.event_type == "policy-update"
    assert document.entries[0].item.confidence == 0.91
    assert (
        document.entries[0].item.why_it_matters
        == "This affects enterprise rollout decisions."
    )
