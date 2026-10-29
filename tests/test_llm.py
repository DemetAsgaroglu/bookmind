from dataclasses import replace

from bookmind.config import get_settings
from bookmind.llm import create_fallback_llms, create_llm


def test_gemini_retry_attempts_come_from_settings():
    settings = replace(
        get_settings(), llm_provider="gemini", google_api_key="test-key", gemini_max_attempts=5
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
