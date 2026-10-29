"""Katalogdan SQLite veritabanini ve FAISS indeksini olusturur.

    python scripts/build_index.py

Kisisel kutuphane verileri korunur; sadece kitaplar ve indeks yenilenir.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bookmind.config import get_settings  # noqa: E402
from bookmind.database import Database  # noqa: E402
from bookmind.vector_store import SentenceTransformerEmbedder, VectorStore  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = Database(settings.db_path)
    count = db.load_catalog(settings.catalog_path)
    print(f"{count} kitap veritabanina yuklendi: {settings.db_path}")

    print(f"Embedding modeli yukleniyor: {settings.embedding_model}")
    embedder = SentenceTransformerEmbedder(settings.embedding_model)

    start = time.perf_counter()
    store = VectorStore.build(db.all_books(), embedder)
    store.save(settings.index_dir)
    print(f"FAISS indeksi olusturuldu ({len(store.book_ids)} vektor, {time.perf_counter() - start:.1f} sn)")


if __name__ == "__main__":
    main()
