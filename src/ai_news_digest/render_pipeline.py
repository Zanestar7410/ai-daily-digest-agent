from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_news_digest.latex import compile_pdf, render_digest_tex
from ai_news_digest.models import DigestDocument, DigestEntry
from ai_news_digest.storage import DigestStorage
from ai_news_digest.topics import format_topic_label


@dataclass
class RenderResult:
    selected_count: int
    tex_path: Path
    pdf_path: Path | None
    topic_tex_paths: dict[str, Path] = field(default_factory=dict)
    topic_pdf_paths: dict[str, Path | None] = field(default_factory=dict)


class DigestRenderPipeline:
    def __init__(self, *, storage: DigestStorage, output_dir: Path) -> None:
        self.storage = storage
        self.output_dir = output_dir

    def run(
        self,
        *,
        document: DigestDocument,
        dry_run: bool = False,
        write_topic_reports: bool = False,
    ) -> RenderResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.output_dir / f"digest-{document.digest_time.date().isoformat()}.tex"
        tex_path.write_text(
            render_digest_tex(
                digest_time=document.digest_time,
                entries=document.entries,
                report_title="AI Daily Digest",
            ),
            encoding="utf-8",
        )

        pdf_path = None if dry_run else compile_pdf(tex_path=tex_path, output_dir=self.output_dir)
        topic_tex_paths: dict[str, Path] = {}
        topic_pdf_paths: dict[str, Path | None] = {}
        if write_topic_reports:
            for topic, entries in self._group_entries_by_topic(document.entries).items():
                topic_tex_path = self.output_dir / (
                    f"topic-{topic}-{document.digest_time.date().isoformat()}.tex"
                )
                topic_tex_path.write_text(
                    render_digest_tex(
                        digest_time=document.digest_time,
                        entries=entries,
                        report_title=f"AI Daily Digest: {format_topic_label(topic)}",
                    ),
                    encoding="utf-8",
                )
                topic_tex_paths[topic] = topic_tex_path
                topic_pdf_paths[topic] = (
                    None if dry_run else compile_pdf(tex_path=topic_tex_path, output_dir=self.output_dir)
                )
        if not dry_run:
            self.storage.initialize()
            self.storage.upsert_items([entry.item for entry in document.entries])
            run_id = self.storage.create_report_run(
                digest_date=document.digest_time,
                pdf_path=str(pdf_path or tex_path),
                report_kind="daily",
                report_topic=None,
                tex_path=str(tex_path),
            )
            self.storage.record_digest_entries(
                run_id,
                [(entry.item, entry.summary, entry.is_backfill) for entry in document.entries],
            )
            for topic, entries in self._group_entries_by_topic(document.entries).items():
                if topic not in topic_tex_paths:
                    continue
                topic_run_id = self.storage.create_report_run(
                    digest_date=document.digest_time,
                    pdf_path=str(topic_pdf_paths[topic] or topic_tex_paths[topic]),
                    report_kind="topic",
                    report_topic=topic,
                    tex_path=str(topic_tex_paths[topic]),
                )
                self.storage.record_digest_entries(
                    topic_run_id,
                    [(entry.item, entry.summary, entry.is_backfill) for entry in entries],
                )
        return RenderResult(
            selected_count=len(document.entries),
            tex_path=tex_path,
            pdf_path=pdf_path,
            topic_tex_paths=topic_tex_paths,
            topic_pdf_paths=topic_pdf_paths,
        )

    def _group_entries_by_topic(self, entries: list[DigestEntry]) -> dict[str, list[DigestEntry]]:
        grouped: dict[str, list[DigestEntry]] = {}
        for entry in entries:
            for topic in entry.item.topics:
                grouped.setdefault(topic, []).append(entry)
        return grouped
