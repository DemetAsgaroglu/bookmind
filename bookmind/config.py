import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    catalog_path: Path
    db_path: Path
    index_dir: Path
    embedding_model: str
    llm_provider: str
    gemini_model: str
    ollama_model: str
    ollama_base_url: str
    google_api_key: str | None
    gemini_fallback_models: list[str]
    gemini_max_attempts: int
    gemini_timeout: int
    max_agent_steps: int
    history_limit: int


def get_settings() -> Settings:
    data_dir = Path(os.getenv("BOOKMIND_DATA_DIR", ROOT_DIR / "data"))
    return Settings(
        catalog_path=data_dir / "books_cleaned.json",
        db_path=data_dir / "bookmind.db",
        index_dir=data_dir / "index",
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        google_api_key=os.getenv("GOOGLE_API_KEY") or None,
        gemini_fallback_models=[
            m.strip()
            for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite,gemini-3.8-flash").split(",")
            if m.strip()
        ],
        gemini_max_attempts=int(os.getenv("GEMINI_MAX_ATTEMPTS", "2")),
        gemini_timeout=int(os.getenv("GEMINI_TIMEOUT", "90")),
        max_agent_steps=int(os.getenv("MAX_AGENT_STEPS", "6")),
        history_limit=int(os.getenv("HISTORY_LIMIT", "12")),
    )
