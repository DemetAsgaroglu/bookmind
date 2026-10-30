import warnings

from langchain_core.language_models import BaseChatModel

from .config import Settings

# Bazi Gemini modelleri sabit sampling kullanir; temperature yok sayilir, her istekte uyari basmasin.
warnings.filterwarnings("ignore", message=r".*uses fixed sampling defaults.*")

# Arkasinda yedek model olan modeller uzun beklemez; tek denemede, bu sure icinde cevap
# vermezse istek siradaki modele gecer.
QUICK_TIMEOUT_SECONDS = 30


def _fallback_models(settings: Settings) -> list[str]:
    return [m for m in dict.fromkeys(settings.gemini_fallback_models) if m != settings.gemini_model]


def _gemini(settings: Settings, model: str, has_fallback: bool = False) -> BaseChatModel:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY tanimli degil. .env dosyasina ekleyin.")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=settings.google_api_key,
        temperature=0.3,
        # SDK'da toplam deneme sayisi (ilk istek dahil). 429/500/502/503/504 hatalarinda
        # 1, 2, 4, 8... saniye bekleyerek tekrar dener.
        max_retries=1 if has_fallback else settings.gemini_max_attempts,
        # Sunucuya da X-Server-Timeout olarak gider; asilirsa 504 DEADLINE_EXCEEDED doner.
        timeout=min(settings.gemini_timeout, QUICK_TIMEOUT_SECONDS) if has_fallback else settings.gemini_timeout,
    )


def create_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "gemini":
        return _gemini(settings, settings.gemini_model, has_fallback=bool(_fallback_models(settings)))

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
    models = _fallback_models(settings)
    return [_gemini(settings, m, has_fallback=i < len(models) - 1) for i, m in enumerate(models)]
