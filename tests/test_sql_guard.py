import pytest

from bookmind.sql_guard import UnsafeQueryError, run_readonly_query, validate_sql


def test_simple_select(db):
    rows = run_readonly_query(db, "SELECT id, title, price FROM books WHERE price < 100 ORDER BY price")
    assert rows
    assert all(r["price"] < 100 for r in rows)


def test_row_limit(db):
    rows = run_readonly_query(db, "SELECT id FROM books")
    assert len(rows) == 20


def test_norm_function_handles_turkish_case(db):
    upper = run_readonly_query(db, "SELECT COUNT(*) AS n FROM books WHERE norm(genre) LIKE norm('%BİLİM KURGU%')")
    lower = run_readonly_query(db, "SELECT COUNT(*) AS n FROM books WHERE norm(genre) LIKE '%bilim kurgu%'")
    assert upper[0]["n"] == lower[0]["n"] > 0


def test_cte_is_allowed(db):
    rows = run_readonly_query(
        db, "WITH ucuz AS (SELECT * FROM books WHERE price < 120) SELECT COUNT(*) AS n FROM ucuz"
    )
    assert rows[0]["n"] > 0


def test_markdown_fence_is_stripped():
    assert validate_sql("```sql\nSELECT 1;\n```") == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM books",
        "DROP TABLE books",
        "UPDATE books SET price = 0",
        "INSERT INTO books (id, title) VALUES ('x', 'y')",
        "SELECT 1; DROP TABLE books",
        "PRAGMA table_info(books)",
        "ATTACH DATABASE 'x.db' AS x",
        "",
    ],
)
def test_rejects_non_select(db, sql):
    with pytest.raises(UnsafeQueryError):
        run_readonly_query(db, sql)


def test_cannot_read_library_table(db):
    db.add_to_library("ayse", "book_001")
    with pytest.raises(UnsafeQueryError):
        run_readonly_query(db, "SELECT * FROM library")
    with pytest.raises(UnsafeQueryError):
        run_readonly_query(db, "SELECT b.title FROM books b JOIN library l ON l.book_id = b.id")


def test_cannot_read_sqlite_master(db):
    with pytest.raises(UnsafeQueryError):
        run_readonly_query(db, "SELECT name FROM sqlite_master")


def test_write_inside_cte_is_blocked(db):
    with pytest.raises(UnsafeQueryError):
        run_readonly_query(db, "WITH x AS (SELECT 1) DELETE FROM books")
    assert run_readonly_query(db, "SELECT COUNT(*) AS n FROM books")[0]["n"] == 536


def test_like_ignores_turkish_chars_on_either_side(db):
    expected = run_readonly_query(db, "SELECT COUNT(*) AS n FROM books WHERE norm(genre) LIKE '%cocuk%'")[0]["n"]
    assert expected > 0
    for sql in [
        "SELECT COUNT(*) AS n FROM books WHERE norm(genre) LIKE '%çocuk%'",
        "SELECT COUNT(*) AS n FROM books WHERE genre LIKE '%ÇOCUK KİTAPLARI%'",
        "SELECT COUNT(*) AS n FROM books WHERE genre LIKE 'cocuk kitaplar_'",
    ]:
        assert run_readonly_query(db, sql)[0]["n"] == expected
    assert run_readonly_query(db, "SELECT COUNT(*) AS n FROM books WHERE genre LIKE 'x!%' ESCAPE '!'")[0]["n"] == 0
