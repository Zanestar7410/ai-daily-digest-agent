from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ai_news_digest.models import EventRecord


class ResearchPlanStep(BaseModel):
    title: str
    question: str


class ResearchPlan(BaseModel):
    query: str
    steps: list[ResearchPlanStep] = Field(default_factory=list)


class ResearchReport(BaseModel):
    query: str
    generated_at: datetime
    executive_summary: str
    plan: ResearchPlan
    key_findings: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    comparison_notes: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)


def render_research_markdown(report: ResearchReport) -> str:
    lines = [
        "# Research Report",
        "",
        f"Query: {report.query}",
        f"Generated At: {report.generated_at.isoformat()}",
        "",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## Research Plan",
    ]
    for index, step in enumerate(report.plan.steps, start=1):
        lines.extend(
            [
                f"{index}. {step.title}",
                f"   Question: {step.question}",
            ]
        )
    lines.extend(["", "## Key Findings"])
    for finding in report.key_findings:
        lines.append(f"- {finding}")
    lines.extend(["", "## Evidence Highlights"])
    if report.evidence_highlights:
        for evidence in report.evidence_highlights:
            lines.append(f"- {evidence}")
    else:
        lines.append("- None")
    lines.extend(["", "## Comparison Notes"])
    if report.comparison_notes:
        for note in report.comparison_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- None")
    lines.extend(["", "## Source Events"])
    for event_id in report.source_event_ids:
        lines.append(f"- {event_id}")
    lines.extend(["", "## Open Questions"])
    if report.open_questions:
        for question in report.open_questions:
            lines.append(f"- {question}")
    else:
        lines.append("- None")
    lines.extend(["", "## Verification Notes"])
    if report.verification_notes:
        for note in report.verification_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- None")
    return "\n".join(lines)


class RuleBasedResearchPlanner:
    def build_plan(self, *, query: str, events: list[EventRecord]) -> ResearchPlan:
        return ResearchPlan(
            query=query,
            steps=[
                ResearchPlanStep(
                    title="梳理近期事件",
                    question="哪些近期事件最直接回答这个研究问题？",
                ),
                ResearchPlanStep(
                    title="比较影响范围",
                    question="这些事件分别影响哪些产品、接口或使用场景？",
                ),
                ResearchPlanStep(
                    title="归纳结论",
                    question="从这些事件中能得到什么清晰结论，还缺什么证据？",
                ),
            ],
        )


class RuleBasedResearchWriter:
    def build_report(
        self,
        *,
        query: str,
        plan: ResearchPlan,
        events: list[EventRecord],
    ) -> ResearchReport:
        ranked = sorted(events, key=lambda event: (event.confidence, event.published_at), reverse=True)
        key_findings = [
            f"{event.title}: {event.why_it_matters or event.summary}"
            for event in ranked[:3]
        ]
        evidence_highlights = [
            f"{event.title} | {event.source_name} | confidence={event.confidence:.2f}"
            for event in ranked[:3]
        ]
        comparison_notes = self._build_comparison_notes(ranked)
        summary = (
            f"本次研究围绕“{query}”整理了 {len(events)} 条相关事件，"
            "优先参考高置信度与最近发布时间的事件。"
        )
        open_questions: list[str] = []
        verification_notes: list[str] = []
        if len(events) < 2:
            open_questions.append("当前事件数量较少，建议补充更多来源后再做结论。")
            verification_notes.append("研究样本较少，结论更适合作为初步观察。")
        if len({event.source_name for event in ranked}) < 2 and ranked:
            verification_notes.append("当前研究主要依赖单一来源，建议增加更多来源做交叉验证。")
        return ResearchReport(
            query=query,
            generated_at=datetime.now(tz=UTC),
            executive_summary=summary,
            plan=plan,
            key_findings=key_findings,
            evidence_highlights=evidence_highlights,
            comparison_notes=comparison_notes,
            source_event_ids=[event.event_id for event in ranked[:5]],
            open_questions=open_questions,
            verification_notes=verification_notes,
        )

    def _build_comparison_notes(self, events: list[EventRecord]) -> list[str]:
        if not events:
            return []

        entity_map: dict[str, set[str]] = {}
        for event in events:
            for entity in event.entities:
                entity_map.setdefault(entity, set()).add(event.event_type or "unknown")

        notes: list[str] = []
        for entity, event_types in entity_map.items():
            if len(event_types) > 1:
                notes.append(
                    f"{entity} 同时涉及 {', '.join(sorted(event_types))}，需要结合不同事件类型综合判断。"
                )
        if not notes:
            notes.append("当前样本中的事件类型较集中，比较分析主要体现在时间和影响范围。")
        return notes


class ResearchReportBuilder:
    def __init__(self, *, planner: object, writer: object) -> None:
        self.planner = planner
        self.writer = writer

    def build(
        self,
        *,
        query: str,
        events: list[EventRecord],
        output_path: Path | None = None,
    ) -> ResearchReport:
        plan = self.planner.build_plan(query=query, events=events)
        report = self.writer.build_report(query=query, plan=plan, events=events)
        if not report.evidence_highlights:
            report.evidence_highlights = [
                f"{event.title} | {event.source_name} | confidence={event.confidence:.2f}"
                for event in events[:3]
            ]
        if not report.comparison_notes:
            report.comparison_notes = ["当前比较分析尚未补充。"]
        if not report.verification_notes:
            report.verification_notes = ["当前研究结果尚未进行额外交叉验证。"]
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(render_research_markdown(report), encoding="utf-8")
        return report


def run_research_mode(
    *,
    query: str,
    events: list[EventRecord],
    output_path: Path | None = None,
    planner: object | None = None,
    writer: object | None = None,
) -> tuple[ResearchReport, str]:
    builder = ResearchReportBuilder(
        planner=planner or RuleBasedResearchPlanner(),
        writer=writer or RuleBasedResearchWriter(),
    )
    report = builder.build(
        query=query,
        events=events,
        output_path=output_path,
    )
    markdown = render_research_markdown(report)
    if output_path is not None and not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    return report, markdown
