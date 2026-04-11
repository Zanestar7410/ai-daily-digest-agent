from datetime import UTC, datetime
from pathlib import Path

from ai_news_digest.models import DigestDocument, DigestEntry, SourceItem
from ai_news_digest.render_pipeline import DigestRenderPipeline
from ai_news_digest.storage import DigestStorage


def test_render_pipeline_writes_tex_in_dry_run(tmp_path: Path) -> None:
    document = DigestDocument(
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        entries=[
            DigestEntry(
                item=SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI updates safety guidance",
                    url="https://openai.com/news/safety-guidance/",
                    published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
                    excerpt="Official summary.",
                    topics=["safety-governance"],
                ),
                summary="summary one",
                is_backfill=False,
            )
        ],
    )
    pipeline = DigestRenderPipeline(
        storage=DigestStorage(tmp_path / "state" / "digest.sqlite3"),
        output_dir=tmp_path / "output",
    )

    result = pipeline.run(document=document, dry_run=True)

    assert result.selected_count == 1
    assert result.pdf_path is None
    assert "summary one" in result.tex_path.read_text(encoding="utf-8")
    assert not (tmp_path / "state" / "digest.sqlite3").exists()


def test_render_pipeline_writes_topic_reports_in_dry_run(tmp_path: Path) -> None:
    document = DigestDocument(
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        entries=[
            DigestEntry(
                item=SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI ships coding agent runtime",
                    url="https://openai.com/news/coding-agent-runtime/",
                    published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
                    excerpt="Official summary.",
                    topics=["coding-agent", "agent-platform"],
                ),
                summary="summary one",
                is_backfill=False,
            )
        ],
    )
    pipeline = DigestRenderPipeline(
        storage=DigestStorage(tmp_path / "state" / "digest.sqlite3"),
        output_dir=tmp_path / "output",
    )

    result = pipeline.run(document=document, dry_run=True, write_topic_reports=True)

    assert "coding-agent" in result.topic_tex_paths
    assert result.topic_tex_paths["coding-agent"].exists()
    assert "OpenAI ships coding agent runtime" in result.topic_tex_paths["coding-agent"].read_text(
        encoding="utf-8"
    )


def test_render_pipeline_persists_event_records_for_non_dry_run(tmp_path: Path, monkeypatch) -> None:
    document = DigestDocument(
        digest_time=datetime(2026, 4, 5, 10, 30, tzinfo=UTC),
        entries=[
            DigestEntry(
                item=SourceItem(
                    source_id="openai_news",
                    source_name="OpenAI News",
                    source_tier=0,
                    title="OpenAI ships coding agent runtime",
                    url="https://openai.com/news/coding-agent-runtime/",
                    published_at=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
                    excerpt="Official summary.",
                    topics=["coding-agent"],
                    entities=["OpenAI", "Responses API"],
                    event_type="product-release",
                ),
                summary="summary one",
                is_backfill=False,
            )
        ],
    )
    pipeline = DigestRenderPipeline(
        storage=DigestStorage(tmp_path / "state" / "digest.sqlite3"),
        output_dir=tmp_path / "output",
    )
    monkeypatch.setattr(
        "ai_news_digest.render_pipeline.compile_pdf",
        lambda *, tex_path, output_dir: output_dir / f"{tex_path.stem}.pdf",
    )

    pipeline.run(document=document, dry_run=False)

    events = DigestStorage(tmp_path / "state" / "digest.sqlite3").search_events(
        query="agent",
        event_type="product-release",
        limit=5,
    )

    assert [event.event_id for event in events] == [
        "https://openai.com/news/coding-agent-runtime/"
    ]
