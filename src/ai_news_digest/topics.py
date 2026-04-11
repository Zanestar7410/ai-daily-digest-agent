from __future__ import annotations


TOPIC_TAXONOMY: tuple[str, ...] = (
    "agent-platform",
    "coding-agent",
    "tool-use",
    "model-release",
    "rag-search",
    "infra-serving",
    "benchmark-eval",
    "safety-governance",
    "open-source-framework",
    "enterprise-application",
)


def format_topic_label(topic: str) -> str:
    return topic.replace("-", " ").title()
