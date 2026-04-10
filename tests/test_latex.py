from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_news_digest.latex import compile_pdf, render_digest_tex
from ai_news_digest.models import DigestEntry, SourceItem


def build_entry(*, title: str, url: str, summary: str, is_backfill: bool) -> DigestEntry:
    item = SourceItem(
        source_id="google_ai_blog",
        source_name="Google AI Blog",
        source_tier=0,
        title=title,
        url=url,
        published_at=datetime(2026, 3, 31, 8, 0, tzinfo=UTC),
        excerpt="Official launch details.",
    )
    return DigestEntry(item=item, summary=summary, is_backfill=is_backfill)


def test_render_digest_tex_includes_source_summary_and_backfill_marker() -> None:
    tex = render_digest_tex(
        digest_time=datetime(2026, 4, 1, 10, 30, tzinfo=UTC),
        entries=[
            build_entry(
                title="Gemini 3.1 Flash",
                url="https://example.com/a",
                summary="这是第一条摘要。",
                is_backfill=False,
            ),
            build_entry(
                title="Claude compliance API",
                url="https://example.com/b",
                summary="这是第二条摘要。",
                is_backfill=True,
            ),
        ],
    )

    assert "AI Daily Digest" in tex
    assert "Google AI Blog" in tex
    assert "这是第一条摘要。" in tex
    assert "Backfilled item" in tex
    assert "\\documentclass[12pt]{article}" in tex
    assert "\\usepackage{xeCJK}" in tex


def test_compile_pdf_avoids_text_decoding_in_subprocess(monkeypatch, tmp_path: Path) -> None:
    tex_path = tmp_path / "sample.tex"
    tex_path.write_text("sample", encoding="utf-8")
    captured: dict[str, object] = {}
    pdf_path = tmp_path / "sample.pdf"

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        pdf_path.write_bytes(b"generated-pdf")

    monkeypatch.setattr("ai_news_digest.latex.subprocess.run", fake_run)

    compile_pdf(tex_path=tex_path, output_dir=tmp_path)

    assert captured["command"][0] == "xelatex"
    assert captured["kwargs"]["check"] is True
    assert "text" not in captured["kwargs"]


def test_compile_pdf_raises_if_output_pdf_is_not_regenerated(monkeypatch, tmp_path: Path) -> None:
    tex_path = tmp_path / "sample.tex"
    tex_path.write_text("sample", encoding="utf-8")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"old-pdf")

    original_mtime = pdf_path.stat().st_mtime_ns

    def fake_run(command, **kwargs):
        return None

    monkeypatch.setattr("ai_news_digest.latex.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="PDF output was not regenerated"):
        compile_pdf(tex_path=tex_path, output_dir=tmp_path)

    assert pdf_path.stat().st_mtime_ns == original_mtime
