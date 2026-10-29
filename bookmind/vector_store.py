"""Kitap aciklamalari icin FAISS tabanli anlamsal arama."""

import json
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np

from .text import build_vocabulary, restore_turkish_chars


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vectors, dtype="float32")


def book_to_text(book: dict) -> str:
    parts = [book.get("title"), book.get("author"), book.get("genre"), book.get("description")]
    return ". ".join(p for p in parts if p)


class VectorStore:
    INDEX_FILE = "books.faiss"
    IDS_FILE = "book_ids.json"
    VOCAB_FILE = "vocabulary.json"

    def __init__(
        self,
        index: faiss.Index,
        book_ids: list[str],
        embedder: Embedder,
        vocabulary: dict[str, str] | None = None,
    ):
        self.index = index
        self.book_ids = book_ids
        self.embedder = embedder
        self.vocabulary = vocabulary or {}

    @classmethod
    def build(cls, books: list[dict], embedder: Embedder) -> "VectorStore":
        texts = [book_to_text(b) for b in books]
        vectors = embedder.encode(texts)
        faiss.normalize_L2(vectors)
        # Normalize edilmis vektorlerde ic carpim = kosinus benzerligi
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return cls(index, [b["id"] for b in books], embedder, build_vocabulary(texts))

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / self.INDEX_FILE))
        (directory / self.IDS_FILE).write_text(json.dumps(self.book_ids), encoding="utf-8")
        (directory / self.VOCAB_FILE).write_text(
            json.dumps(self.vocabulary, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path, embedder: Embedder) -> "VectorStore":
        index_path = directory / cls.INDEX_FILE
        if not index_path.exists():
            raise FileNotFoundError(
                f"{index_path} bulunamadi. Once `python scripts/build_index.py` calistirin."
            )
        index = faiss.read_index(str(index_path))
        book_ids = json.loads((directory / cls.IDS_FILE).read_text(encoding="utf-8"))
        # Eski indekslerde sozluk dosyasi yok; o durumda sorgu oldugu gibi aranir
        vocab_path = directory / cls.VOCAB_FILE
        vocabulary = json.loads(vocab_path.read_text(encoding="utf-8")) if vocab_path.exists() else {}
        return cls(index, book_ids, embedder, vocabulary)

    def search(
        self, query: str, k: int = 5, exclude: set[str] | None = None
    ) -> list[tuple[str, float]]:
        exclude = exclude or set()
        query_vec = self.embedder.encode([restore_turkish_chars(query, self.vocabulary)])
        faiss.normalize_L2(query_vec)
        # Haric tutulacak kitaplar elendikten sonra da k sonuc kalsin diye fazladan aliyoruz.
        fetch = min(len(self.book_ids), k + len(exclude))
        scores, positions = self.index.search(query_vec, fetch)
        results = []
        for score, pos in zip(scores[0], positions[0]):
            if pos < 0:
                continue
            book_id = self.book_ids[pos]
            if book_id in exclude:
                continue
            results.append((book_id, float(score)))
            if len(results) == k:
                break
        return results
