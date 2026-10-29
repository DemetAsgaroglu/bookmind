import json

import pytest

from bookmind.rules import quick_reply
from bookmind.text import build_vocabulary, normalize, restore_turkish_chars
from bookmind.tools import build_tools


def test_catalog_loaded(db):
    assert len(db.all_books()) == 536


def test_library_crud(db):
    db.add_to_library("demet", "book_010", "okudum", 5)
    db.add_to_library("demet", "book_020", "okuyacagim")
    items = {i["id"]: i for i in db.get_library("demet")}
    assert items["book_010"]["rating"] == 5
    assert items["book_020"]["status"] == "okuyacagim"

    db.add_to_library("demet", "book_020", "okuyorum")
    assert {i["id"]: i for i in db.get_library("demet")}["book_020"]["status"] == "okuyorum"

    assert db.remove_from_library("demet", "book_010")
    assert not db.remove_from_library("demet", "book_010")
    assert db.get_library("baska_kullanici") == []


def test_library_validation(db):
    with pytest.raises(KeyError):
        db.add_to_library("demet", "book_999999")
    with pytest.raises(ValueError):
        db.add_to_library("demet", "book_001", status="bitirdim")
    with pytest.raises(ValueError):
        db.add_to_library("demet", "book_001", rating=7)


def test_search_excludes_library_books(db, store):
    query = db.get_book("book_005")["title"]
    first_hit = store.search(query, k=1)[0][0]
    db.add_to_library("demet", first_hit)

    tools = {t.name: t for t in build_tools(db, store, "demet")}
    results = json.loads(tools["search_books"].invoke({"query": query, "limit": 5}))
    assert first_hit not in {r["id"] for r in results}

    other = {t.name: t for t in build_tools(db, store, "ali")}
    results = json.loads(other["search_books"].invoke({"query": query, "limit": 5}))
    assert first_hit in {r["id"] for r in results}


def test_library_tool_is_scoped_to_user(db, store):
    db.add_to_library("demet", "book_001", rating=4)
    db.add_to_library("ali", "book_002")
    tools = {t.name: t for t in build_tools(db, store, "demet")}
    library = json.loads(tools["get_my_library"].invoke({}))
    assert [i["id"] for i in library] == ["book_001"]


def test_query_tool_returns_error_text_instead_of_raising(db, store):
    tools = {t.name: t for t in build_tools(db, store, "demet")}
    assert tools["query_catalog"].invoke({"sql": "DROP TABLE books"}).startswith("Sorgu reddedildi")
    assert tools["query_catalog"].invoke({"sql": "SELECT yok FROM books"}).startswith("SQL hatasi")


@pytest.mark.parametrize("text", ["Merhaba", "selam!", "Günaydın", "Teşekkürler", "çok sağol"])
def test_quick_reply_matches_short_messages(text):
    assert quick_reply(text) is not None


@pytest.mark.parametrize(
    "text", ["Merhaba, polisiye önerir misin?", "teşekkürler bir tane daha öner", "kod yazmayı öğreten kitap"]
)
def test_quick_reply_ignores_real_questions(text):
    assert quick_reply(text) is None


def test_normalize():
    assert normalize("Ahmet ÜMİT") == normalize("ahmet umit") == "ahmet umit"
    assert normalize("IŞIK") == "isik"


def test_restore_turkish_chars():
    vocabulary = build_vocabulary(["Şiir kitabı", "Çocuklar için masal", "şiir", "Şiir"])
    assert restore_turkish_chars("siir kitabi", vocabulary) == "şiir kitabı"
    assert restore_turkish_chars("Cocuklar icin masal", vocabulary) == "çocuklar için masal"
    # Turkce karakterli veya sozlukte olmayan kelimeler degismez
    assert restore_turkish_chars("şiir romanı python", vocabulary) == "şiir romanı python"


def test_search_handles_queries_without_turkish_chars(store):
    assert store.search("siir kitabi", k=5) == store.search("şiir kitabı", k=5)
