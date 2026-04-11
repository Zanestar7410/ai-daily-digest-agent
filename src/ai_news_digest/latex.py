from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from ai_news_digest.models import DigestEntry


TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "daily_digest.tex"


LATEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value: str) -> str:
    return "".join(LATEX_ESCAPE.get(char, char) for char in value)


def render_digest_tex(
    *,
    digest_time: datetime,
    entries: list[DigestEntry],
    report_title: str = "AI Daily Digest",
) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    entry_blocks: list[str] = []
    for index, entry in enumerate(entries, start=1):
        backfill_note = (
            "\\textbf{Backfilled item}\\\\\n" if entry.is_backfill else ""
        )
        entry_blocks.append(
            "\n".join(
                [
                    rf"\subsection*{{{index}. {escape_latex(entry.item.title)}}}",
                    rf"\textbf{{Source}}: {escape_latex(entry.item.source_name)}\\",
                    rf"\textbf{{Published}}: {entry.item.published_at.date().isoformat()}\\",
                    rf"\textbf{{URL}}: \url{{{entry.item.url}}}\\",
                    backfill_note + rf"\textbf{{Summary}}: {escape_latex(entry.summary)}",
                ]
            )
        )

    return (
        template.replace("{{REPORT_TITLE}}", escape_latex(report_title))
        .replace("{{RUN_DATE}}", digest_time.date().isoformat())
        .replace("{{ENTRY_COUNT}}", str(len(entries)))
        .replace("{{ENTRIES}}", "\n\n".join(entry_blocks))
    )


def compile_pdf(*, tex_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    previous_mtime_ns = pdf_path.stat().st_mtime_ns if pdf_path.exists() else None
    command = [
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={output_dir}",
        str(tex_path),
    ]
    for _ in range(2):
        subprocess.run(command, check=True)

    if not pdf_path.exists():
        raise RuntimeError(f"PDF output was not regenerated: {pdf_path}")

    if previous_mtime_ns is not None and pdf_path.stat().st_mtime_ns == previous_mtime_ns:
        raise RuntimeError(f"PDF output was not regenerated: {pdf_path}")

    return pdf_path
