# movie_night_db.py
from __future__ import annotations
import sqlite3, threading, atexit
from settings import DATABASE_PATH as _DB_PATH, SCHEMA_PATH as _SCHEMA_PATH

# ─── internal state ─────────────────────────────────────────────────────
_thread_local = threading.local()   # holds .conn per thread
_init_lock    = threading.Lock()    # serialize first-time schema init
_write_lock   = threading.RLock()   # for SERIALISE_WRITES
_SCHEMA_DONE  = False               # process-wide flag

SERIALISE_WRITES = False            # flip True if you see “database is locked”

# ─── internal helpers ────────────────────────────────────────────────────
def _new_connection() -> sqlite3.Connection:
    """Create a fresh sqlite3.Connection and run schema SQL once per process."""
    conn = sqlite3.connect(
        _DB_PATH,
        check_same_thread=True,     # each thread uses its OWN connection
        isolation_level="DEFERRED",
    )
    conn.row_factory = sqlite3.Row

    global _SCHEMA_DONE
    if not _SCHEMA_DONE:
        with _init_lock:
            if not _SCHEMA_DONE:
                ddl = _SCHEMA_PATH.read_text()
                conn.executescript(ddl)
                conn.commit()
                _SCHEMA_DONE = True

    return conn

# bootstrap the “main” connection now
_root_conn = _new_connection()

# ─── public helpers ──────────────────────────────────────────────────────
def connection() -> sqlite3.Connection:
    """
    Return this thread’s sqlite3.Connection, creating it on first use.
    Main (importing) thread gets `_root_conn`; workers call `attach_thread()`
    to get their own.
    """
    conn = getattr(_thread_local, "conn", None)
    return conn if conn is not None else _root_conn

def attach_thread() -> None:
    """
    Call once at the start of each worker thread *before* any SQL helpers.
    Ensures that _thread_local.conn is set via _new_connection (and thus
    does schema-init guard correctly).
    """
    if not hasattr(_thread_local, "conn"):
        _thread_local.conn = _new_connection()

def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """
    Like `connection().execute(...)`, but can serialize writes if needed.
    """
    conn = connection()
    cur  = conn.cursor()
    if SERIALISE_WRITES and sql.lstrip().upper().startswith(
        ("INSERT", "UPDATE", "DELETE", "REPLACE")
    ):
        with _write_lock:
            return cur.execute(sql, params)
    return cur.execute(sql, params)

def executemany(sql: str, seq: list[tuple]) -> sqlite3.Cursor:
    """
    Like `connection().executemany(...)`.
    Returns the cursor so callers can read lastrowid if desired.
    """
    conn = connection()
    cur  = conn.cursor()
    if SERIALISE_WRITES and sql.lstrip().upper().startswith(
        ("INSERT", "UPDATE", "DELETE", "REPLACE")
    ):
        with _write_lock:
            cur.executemany(sql, seq)
    else:
        cur.executemany(sql, seq)
    return cur

def commit() -> None:
    """Commit the current thread’s Connection."""
    connection().commit()

# ─── cleanup ──────────────────────────────────────────────────────────────
@atexit.register
def _close_everything() -> None:
    """Close every thread-local connection on exit."""
    # close worker conns
    for conn in (getattr(_thread_local, "conn", None),):
        if isinstance(conn, sqlite3.Connection):
            conn.close()
    # close root
    if isinstance(_root_conn, sqlite3.Connection):
        _root_conn.close()
