from __future__ import annotations
import sqlite3, threading, atexit

from settings import DATABASE_PATH as _DB_PATH, SCHMA_PATH as _SCHMA_PATH

# --- internal state ---------------------------------------------------------
_thread_local = threading.local()           # holds .conn per thread
_init_lock    = threading.Lock()             # makes schema init once
_write_lock   = threading.RLock()            # SERIALISE_WRITES = True uses this

SERIALISE_WRITES = False   # flip to True if you see "database is locked" errors


# ─────────────────────────────────────────────────────────────────────────────
# public helpers
# ─────────────────────────────────────────────────────────────────────────────
def connection() -> sqlite3.Connection:
    """Return the thread-local sqlite3 connection (create on first use)."""
    if getattr(_thread_local, "conn", None) is None:
        _thread_local.conn = _new_connection()

    return _thread_local.conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """Proxy helper used by repo: auto-adds write-lock if requested."""
    conn = connection()
    cur  = conn.cursor()

    if SERIALISE_WRITES and sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
        with _write_lock:
            return cur.execute(sql, params)
    return cur.execute(sql, params)


def executemany(sql: str, seq: list[tuple]) -> None:
    conn = connection()
    cur  = conn.cursor()
    if SERIALISE_WRITES and sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
        with _write_lock:
            cur.executemany(sql, seq)
    else:
        cur.executemany(sql, seq)


def commit() -> None:
    connection().commit()


# ─────────────────────────────────────────────────────────────────────────────
# internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _new_connection() -> sqlite3.Connection:
    """Create a new sqlite3 connection (per thread)."""
    conn = sqlite3.connect(
        _DB_PATH,
        check_same_thread=True,      # OK – every thread gets its own object
        isolation_level="DEFERRED",  # default; explicit commit() needed
    )
    conn.row_factory = sqlite3.Row

    # first thread initialises schema exactly once
    if not getattr(_thread_local, "_schema_done", False):
        with _init_lock:
            if not getattr(_thread_local, "_schema_done", False):
                _initialize_schema(conn)
                _thread_local._schema_done = True

    return conn


def _initialize_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql if tables don’t exist yet (idempotent)."""
    ddl = _SCHMA_PATH.read_text()
    conn.executescript(ddl)
    conn.commit()


# close dangling connections when Python exits
@atexit.register
def _close_everything() -> None:
    conns = [getattr(tl, "conn", None) for tl in (_thread_local,)]
    for c in conns:
        if c is not None:
            c.close()