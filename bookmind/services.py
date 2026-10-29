from dataclasses import dataclass

from .agent import BookAgent
from .config import Settings, get_settings
from .database import Database
from .llm import create_fallback_llms, create_llm
from .vector_store import SentenceTransformerEmbedder, VectorStore


@dataclass
class Services:
    db: Database
    store: VectorStore
    agent: BookAgent | None


def create_services(settings: Settings | None = None, with_agent: bool = True) -> Services:
    settings = settings or get_settings()
    if not settings.db_path.exists():
        raise FileNotFoundError(
            f"{settings.db_path} bulunamadi. Once `python scripts/build_index.py` calistirin."
        )
    db = Database(settings.db_path)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    store = VectorStore.load(settings.index_dir, embedder)
    agent = None
    if with_agent:
        agent = BookAgent(
            create_llm(settings),
            db,
            store,
            max_steps=settings.max_agent_steps,
            history_limit=settings.history_limit,
            fallback_llms=create_fallback_llms(settings),
        )
    return Services(db=db, store=store, agent=agent)
