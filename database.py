import os
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def get_conn():
    conn = sqlite3.connect(os.environ.get("OS_DB", "ordens.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    finally:
        conn.close()


def get_db():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()
