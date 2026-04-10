from pathlib import Path

from ai_news_digest.config import load_search_registry


def test_load_default_search_registry() -> None:
    registry = load_search_registry(Path("config/search_sources.json"))

    assert [source.id for source in registry] == [
        "openai_news",
        "anthropic_claude_blog",
        "google_ai_blog",
        "meta_ai_blog",
        "hugging_face_blog",
        "microsoft_ai_blog",
        "nature_machine_learning",
        "mit_technology_review_ai",
        "github_community_ai",
    ]
    assert registry[0].domains == ["openai.com"]
    assert registry[-1].tier == 2
