"""Model tarafindan uretilen SQL sorgularini guvenli sekilde calistirir.

Uc katmanli koruma var:
1. Metin kontrolu: tek bir SELECT/WITH ifadesi olmali.
2. SQLite authorizer: sadece `books` tablosundan okumaya izin verilir.
   Boylece model `library` tablosu uzerinden baska kullanicilarin verisine ulasamaz.
3. Salt okunur baglanti, satir limiti ve zaman asimi.
"""

import re
import sqlite3
import time

from .database import Database

ALLOWED_TABLES = {"books"}
MAX_ROWS = 20
TIMEOUT_SECONDS = 2.0

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION}
_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class UnsafeQueryError(ValueError):
    pass


def validate_sql(sql: str) -> str:
    # Model bazen sorguyu ```sql blogu icinde dondurur.
    sql = re.sub(r"^\s*```(?:sql)?\s*|\s*```\s*$", "", sql, flags=re.IGNORECASE)
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise UnsafeQueryError("Bos sorgu.")
    if ";" in sql:
        raise UnsafeQueryError("Tek bir sorguya izin veriliyor.")
    if not _START.match(sql):
        raise UnsafeQueryError("Sadece SELECT sorgularina izin veriliyor.")
    return sql


def _authorizer(action, arg1, arg2, db_name, trigger):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 in ALLOWED_TABLES else sqlite3.SQLITE_DENY
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def run_readonly_query(db: Database, sql: str, max_rows: int = MAX_ROWS) -> list[dict]:
    sql = validate_sql(sql)
    conn = db.connect_readonly()
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        conn.set_authorizer(_authorizer)
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(max_rows)
        return [dict(r) for r in rows]
    except sqlite3.DatabaseError as exc:
        message = str(exc)
        if "not authorized" in message or "prohibited" in message:
            raise UnsafeQueryError("Sorgu izin verilmeyen bir tabloya veya islem turune erisiyor.") from exc
        if "interrupted" in message:
            raise UnsafeQueryError("Sorgu zaman asimina ugradi.") from exc
        raise
    finally:
        conn.close()
