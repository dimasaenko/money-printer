import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.utils import utils

_DB_PATH = os.path.join(utils.storage_dir("data", create=True), "channels.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    niche TEXT NOT NULL DEFAULT '',
    target_audience TEXT NOT NULL DEFAULT '',
    tone TEXT NOT NULL DEFAULT '',
    content_notes TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT 'en',
    video_length_preset TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'active',
    voice_config TEXT NOT NULL DEFAULT '{}',
    music_config TEXT NOT NULL DEFAULT '{}',
    video_source_config TEXT NOT NULL DEFAULT '{}',
    youtube_config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute(_SCHEMA)
    logger.info(f"channel database initialized at {_DB_PATH}")


# JSON fields that are stored as text but returned as parsed objects
_JSON_FIELDS = {"content_notes", "voice_config", "music_config", "video_source_config", "youtube_config"}


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in _JSON_FIELDS:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _serialize_json_fields(data: dict) -> dict:
    """Convert list/dict fields to JSON strings for storage."""
    out = {}
    for k, v in data.items():
        if k in _JSON_FIELDS and not isinstance(v, str):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out


def create_channel(data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    data = _serialize_json_fields(data)
    data.setdefault("created_at", now)
    data.setdefault("updated_at", now)

    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))

    with _get_conn() as conn:
        cursor = conn.execute(
            f"INSERT INTO channels ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        return get_channel(cursor.lastrowid)


def get_channel(channel_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_channel_by_slug(slug: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM channels WHERE slug = ?", (slug,)).fetchone()
        return _row_to_dict(row) if row else None


def list_channels(status: Optional[str] = None) -> list[dict]:
    with _get_conn() as conn:
        if status:
            rows = conn.execute("SELECT * FROM channels WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM channels ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]


def update_channel(channel_id: int, data: dict) -> Optional[dict]:
    data = _serialize_json_fields(data)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in data.keys())
    values = list(data.values()) + [channel_id]

    with _get_conn() as conn:
        conn.execute(f"UPDATE channels SET {set_clause} WHERE id = ?", values)
    return get_channel(channel_id)


def delete_channel(channel_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        return cursor.rowcount > 0
