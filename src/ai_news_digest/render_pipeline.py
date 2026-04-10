from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_news_digest.latex import compile_pdf, render_digest_tex
from ai_news_digest.models import DigestDocument
from ai_news_digest.storage import DigestStorage


@dataclass
class RenderResult:
    selected_count: int
    tex_path: Path
    pdf_path: Path | None


class DigestRenderPipeline:
    def __init__(self, *, storage: DigestStorage, output_dir: Path) -> None:
        self.storage = storage
        self.output_dir = output_dir

    def run(self, *, document: DigestDocument, dry_run: bool = False) -> RenderResult:
        self.storage.initialize()
        self.storage.upsert_items([entry.item for entry in document.entries])

        self.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.output_dir / f"digest-{document.digest_time.date().isoformat()}.tex"
        tex_path.write_text(
            render_digest_tex(digest_time=document.digest_time, entries=document.entries),
            encoding="utf-8",
        )

        pdf_path = None if dry_run else compile_pdf(tex_path=tex_path, output_dir=self.output_dir)
        run_id = self.storage.create_digest_run(
            digest_date=document.digest_time,
            pdf_path=str(pdf_path or tex_path),
        )
        self.storage.record_digest_entries(
            run_id,
            [(entry.item, entry.summary, entry.is_backfill) for entry in document.entries],
        )
        return RenderResult(
            selected_count=len(document.entries),
            tex_path=tex_path,
            pdf_path=pdf_path,
        )
