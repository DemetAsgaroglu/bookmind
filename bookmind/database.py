"""SQLite katmani: kitap katalogu ve kullanicilarin kisisel kutuphanesi."""

import json
import re
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from .text import normalize

LIBRARY_STATUSES = ("okudum", "okuyorum", "okuyacagim")

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    genre TEXT,
    price INTEGER,
    description TEXT
);

CREATE TABLE IF NOT EXISTS library (
    user_id TEXT NOT NULL,
    book_id TEXT NOT NULL REFERENCES books(id),
    status TEXT NOT NULL CHECK (status IN ('okudum', 'okuyorum', 'okuyacagim')),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, book_id)
);
"""


@lru_cache(maxsize=256)
def _like_regex(pattern: str, escape: str | None) -> re.Pattern:
    parts, chars, i = [], normalize(pattern), 0
    while i < len(chars):
        c = chars[i]
        if escape and c == escape and i + 1 < len(chars):
            parts.append(re.escape(chars[i + 1]))
            i += 2
            continue
        parts.append(".*" if c == "%" else "." if c == "_" else re.escape(c))
        i += 1
    return re.compile("".join(parts), re.DOTALL)


def _like(pattern, value, escape=None):
    """LIKE'i Turkce karakter ve buyuk/kucuk harften bagimsiz yapar.

    Model bazen norm(genre) LIKE '%çocuk%' gibi tek tarafi sadelestirilmis sorgu yaziyor;
    iki taraf da normalize edildigi icin bu sorgular da dogru eslesir.
    """
    if pattern is None or value is None:
        return None
    return _like_regex(str(pattern), escape).fullmatch(normalize(str(value))) is not None


def _register_functions(conn: sqlite3.Connection) -> None:
    conn.create_function("norm", 1, normalize, deterministic=True)
    conn.create_function("like", 2, _like, deterministic=True)
    conn.create_function("like", 3, _like, deterministic=True)


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _register_functions(conn)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def connect_readonly(self) -> sqlite3.Connection:
        """Text-to-SQL icin yalnizca okuma izni olan baglanti."""
        uri = Path(self.path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        _register_functions(conn)
        return conn

    # Katalog

    def load_catalog(self, catalog_path: Path | str) -> int:
        with open(catalog_path, encoding="utf-8") as f:
            books = json.load(f)
        rows = [
            (
                b["id"],
                b["title"].strip(),
                (b.get("author") or "").strip(),
                (b.get("genre") or "").strip(),
                b.get("price"),
                (b.get("description") or "").strip(),
            )
            for b in books
        ]
        with self.connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO books (id, title, author, genre, price, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def all_books(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_book(self, book_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None

    def get_books(self, book_ids: list[str]) -> dict[str, dict]:
        if not book_ids:
            return {}
        placeholders = ",".join("?" for _ in book_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM books WHERE id IN ({placeholders})", book_ids
            ).fetchall()
        return {r["id"]: dict(r) for r in rows}

    # Kisisel kutuphane

    def add_to_library(
        self, user_id: str, book_id: str, status: str = "okudum", rating: int | None = None
    ) -> None:
        if status not in LIBRARY_STATUSES:
            raise ValueError(f"Gecersiz durum: {status}. Secenekler: {', '.join(LIBRARY_STATUSES)}")
        if rating is not None and not 1 <= rating <= 5:
            raise ValueError("Puan 1 ile 5 arasinda olmali.")
        if self.get_book(book_id) is None:
            raise KeyError(f"Kitap bulunamadi: {book_id}")
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO library (user_id, book_id, status, rating) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, book_id) DO UPDATE SET status = excluded.status, "
                "rating = excluded.rating",
                (user_id, book_id, status, rating),
            )

    def remove_from_library(self, user_id: str, book_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "DELETE FROM library WHERE user_id = ? AND book_id = ?", (user_id, book_id)
            )
        return cur.rowcount > 0

    def get_library(self, user_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT b.id, b.title, b.author, b.genre, l.status, l.rating, l.added_at "
                "FROM library l JOIN books b ON b.id = l.book_id "
                "WHERE l.user_id = ? ORDER BY l.added_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def library_book_ids(self, user_id: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT book_id FROM library WHERE user_id = ?", (user_id,)
            ).fetchall()
        return {r["book_id"] for r in rows}
