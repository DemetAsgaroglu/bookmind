import warnings

from langchain_core.language_models import BaseChatModel

from .config import Settings

# Bazi Gemini modelleri sabit sampling kullanir; temperature yok sayilir, her istekte uyari basmasin.
warnings.filterwarnings("ignore", message=r".*uses fixed sampling defaults.*")


def _gemini(settings: Settings, model: str) -> BaseChatModel:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY tanimli degil. .env dosyasina ekleyin.")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=settings.google_api_key,
        temperature=0.3,
        # SDK'da toplam deneme sayisi (ilk istek dahil). 429/500/502/503/504 hatalarinda
        # 1, 2, 4, 8... saniye bekleyerek tekrar dener.
        max_retries=settings.gemini_max_attempts,
        # Sunucuya da X-Server-Timeout olarak gider; asilirsa 504 DEADLINE_EXCEEDED doner.
        timeout=settings.gemini_timeout,
    )


def create_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "gemini":
        return _gemini(settings, settings.gemini_model)

    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.3,
        )

    raise ValueError(f"Bilinmeyen LLM_PROVIDER: {settings.llm_provider} (gemini veya ollama olmali)")


def create_fallback_llms(settings: Settings) -> list[BaseChatModel]:
    """Ana model yogunluk, kota veya zaman asimi yuzunden cevap veremezse sirayla denenecek modeller."""
    if settings.llm_provider != "gemini":
        return []
    models = [m for m in dict.fromkeys(settings.gemini_fallback_models) if m != settings.gemini_model]
    return [_gemini(settings, m) for m in models]
