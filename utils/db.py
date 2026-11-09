import os
import sqlite3
from pathlib import Path

from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            extension TEXT,
            size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_message(role: str, content: str):
    conn = get_connection()
    conn.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()


def get_history(limit: int = 30):
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, created_at FROM chat_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows[::-1]]


def clear_history():
    conn = get_connection()
    conn.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()


def save_upload_meta(filename: str, extension: str, size: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO uploads_meta (filename, extension, size) VALUES (?, ?, ?)",
        (filename, extension, size),
    )
    conn.commit()
    conn.close()
