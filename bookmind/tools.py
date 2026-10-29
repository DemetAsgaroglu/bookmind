"""Agent'in kullandigi araclar.

Araclar her istek icin ilgili kullaniciya gore olusturulur. Kullanici kimligi
modelin eline hic verilmez; boylece model baska bir kullanicinin kutuphanesini
isteyemez.
"""

import json

from langchain_core.tools import StructuredTool

from .database import Database
from .sql_guard import UnsafeQueryError, run_readonly_query
from .vector_store import VectorStore

DESCRIPTION_CHARS = 220

CATALOG_SCHEMA = """books(
  id TEXT,          -- ornek: 'book_042'
  title TEXT,       -- kitap adi
  author TEXT,      -- yazar(lar), virgulle ayrilmis olabilir
  genre TEXT,       -- tur, birden fazlaysa virgulle ayrilir. Ornek: 'Bilim Kurgu', 'Polisiye, Macera'
  price INTEGER,    -- TL cinsinden fiyat
  description TEXT  -- kitap ozeti
)"""


def _short(text: str | None) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= DESCRIPTION_CHARS else text[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "..."


def _format_books(books: list[dict]) -> str:
    return json.dumps(
        [
            {
                "id": b["id"],
                "baslik": b["title"],
                "yazar": b.get("author"),
                "tur": b.get("genre"),
                "fiyat": b.get("price"),
                "ozet": _short(b.get("description")),
            }
            for b in books
        ],
        ensure_ascii=False,
    )


def build_tools(db: Database, store: VectorStore, user_id: str) -> list[StructuredTool]:
    def search_books(query: str, limit: int = 5) -> str:
        limit = max(1, min(limit, 10))
        exclude = db.library_book_ids(user_id)
        hits = store.search(query, k=limit, exclude=exclude)
        books = db.get_books([book_id for book_id, _ in hits])
        ordered = [books[book_id] for book_id, _ in hits if book_id in books]
        if not ordered:
            return "Uygun kitap bulunamadi."
        return _format_books(ordered)

    def query_catalog(sql: str) -> str:
        try:
            rows = run_readonly_query(db, sql)
        except UnsafeQueryError as exc:
            return f"Sorgu reddedildi: {exc}"
        except Exception as exc:  # noqa: BLE001 - hatayi modele geri bildirip duzeltmesini istiyoruz
            return f"SQL hatasi: {exc}. Sorguyu duzeltip tekrar dene."
        if not rows:
            return "Sorgu sonuc dondurmedi."
        for row in rows:
            if "description" in row:
                row["description"] = _short(row["description"])
        return json.dumps(rows, ensure_ascii=False, default=str)

    def get_my_library() -> str:
        items = db.get_library(user_id)
        if not items:
            return "Kullanicinin kutuphanesi bos."
        return json.dumps(
            [
                {
                    "id": i["id"],
                    "baslik": i["title"],
                    "yazar": i["author"],
                    "tur": i["genre"],
                    "durum": i["status"],
                    "puan": i["rating"],
                }
                for i in items
            ],
            ensure_ascii=False,
        )

    return [
        StructuredTool.from_function(
            search_books,
            name="search_books",
            description=(
                "Konuya, temaya, atmosfere veya benzerlige gore anlamsal kitap aramasi yapar. "
                "Ornek: 'uzayda gecen karanlik bir hikaye', 'motivasyon veren bir kitap'. "
                "Kullanicinin kutuphanesindeki kitaplar sonuclardan otomatik olarak cikarilir."
            ),
        ),
        StructuredTool.from_function(
            query_catalog,
            name="query_catalog",
            description=(
                "Katalog uzerinde salt okunur SQLite SELECT sorgusu calistirir. Fiyat, yazar, tur, "
                "sayma ve siralama gibi kesin filtreler icin kullan. En fazla 20 satir doner.\n"
                f"Sema:\n{CATALOG_SCHEMA}\n"
                "Metin karsilastirmalarinda Turkce karakter ve buyuk/kucuk harf farkini onlemek icin "
                "norm() fonksiyonunu kullan: WHERE norm(author) LIKE '%' || norm('Ahmet Umit') || '%'. "
                "Bir kitabin birden fazla turu olabildigi icin turu = ile degil LIKE ile filtrele: "
                "WHERE norm(genre) LIKE '%bilim kurgu%'. "
                "Sadece books tablosuna erisebilirsin."
            ),
        ),
        StructuredTool.from_function(
            get_my_library,
            name="get_my_library",
            description=(
                "Kullanicinin kisisel kutuphanesini getirir: okudugu, okumakta oldugu ve okumak "
                "istedigi kitaplar ile verdigi puanlar. Kisisellestirilmis oneri icin kullan."
            ),
        ),
    ]
