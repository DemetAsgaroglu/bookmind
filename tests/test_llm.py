from dataclasses import replace

from bookmind.config import get_settings
from bookmind.llm import create_fallback_llms, create_llm


def test_gemini_retry_attempts_come_from_settings():
    settings = replace(
        get_settings(), llm_provider="gemini", google_api_key="test-key", gemini_max_attempts=5,
        gemini_fallback_models=[],
    )
    assert create_llm(settings).max_retries == 5


def test_gemini_fallback_models():
    settings = replace(get_settings(), llm_provider="gemini", google_api_key="test-key")
    models = create_fallback_llms(
        replace(settings, gemini_model="a", gemini_fallback_models=["b", "a", "c", "b"])
    )
    assert [m.model.split("/")[-1] for m in models] == ["b", "c"]
    assert create_fallback_llms(replace(settings, gemini_fallback_models=[])) == []
    assert create_fallback_llms(replace(settings, llm_provider="ollama")) == []


def test_models_with_fallback_give_up_quickly():
    settings = replace(
        get_settings(),
        llm_provider="gemini",
        google_api_key="test-key",
        gemini_model="a",
        gemini_fallback_models=["b", "c"],
        gemini_max_attempts=2,
        gemini_timeout=90,
    )
    primary, *fallbacks = [create_llm(settings), *create_fallback_llms(settings)]
    assert [(m.max_retries, m.timeout) for m in (primary, *fallbacks)] == [(1, 30), (1, 30), (2, 90)]

    alone = create_llm(replace(settings, gemini_fallback_models=[]))
    assert (alone.max_retries, alone.timeout) == (2, 90)
