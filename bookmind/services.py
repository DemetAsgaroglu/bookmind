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


def create_services(
    settings: Settings | None = None, with_agent: bool = True, build_if_missing: bool = False
) -> Services:
    """build_if_missing: veritabani veya indeks yoksa katalogdan olusturur (Streamlit Cloud gibi
    dosyalarin repoda olmadigi ortamlar icin)."""
    settings = settings or get_settings()
    index_ready = (settings.index_dir / VectorStore.INDEX_FILE).exists()
    if not build_if_missing and not settings.db_path.exists():
        raise FileNotFoundError(
            f"{settings.db_path} bulunamadi. Once `python scripts/build_index.py` calistirin."
        )
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    if build_if_missing and (not index_ready or not db.all_books()):
        db.load_catalog(settings.catalog_path)
        store = VectorStore.build(db.all_books(), embedder)
        store.save(settings.index_dir)
    else:
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
