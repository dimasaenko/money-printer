import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.utils import utils

_DB_PATH = os.path.join(utils.storage_dir("data", create=True), "channels.db")

VIDEO_STATUS_IDEA = "idea"
VIDEO_STATUS_CONFIGURED = "configured"
VIDEO_STATUS_IN_PROGRESS = "in_progress"
VIDEO_STATUS_COMPLETED = "completed"
VIDEO_STATUS_FAILED = "failed"

VIDEO_STATUSES = {
    VIDEO_STATUS_IDEA,
    VIDEO_STATUS_CONFIGURED,
    VIDEO_STATUS_IN_PROGRESS,
    VIDEO_STATUS_COMPLETED,
    VIDEO_STATUS_FAILED,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    idea_id INTEGER,
    title TEXT NOT NULL,
    video_config TEXT NOT NULL DEFAULT '{}',
    video_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'idea',
    error TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_JSON_FIELDS = {"video_config"}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute(_SCHEMA)
    logger.info(f"videos table initialized at {_DB_PATH}")


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for field in _JSON_FIELDS:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _serialize_json_fields(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k in _JSON_FIELDS and not isinstance(v, str):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out


def create_video(
    channel_id: int,
    title: str,
    video_config: Optional[dict] = None,
    idea_id: Optional[int] = None,
    status: str = VIDEO_STATUS_IDEA,
    task_id: str = "",
) -> dict:
    if status not in VIDEO_STATUSES:
        raise ValueError(f"invalid status: {status}")
    now = datetime.now(timezone.utc).isoformat()
    video_config = video_config or {}
    with _get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO videos (channel_id, idea_id, title, video_config, status, "
            "task_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_id,
                idea_id,
                title,
                json.dumps(video_config, ensure_ascii=False),
                status,
                task_id,
                now,
                now,
            ),
        )
        video_id = cursor.lastrowid
    return {
        "id": video_id,
        "channel_id": channel_id,
        "idea_id": idea_id,
        "title": title,
        "video_config": video_config,
        "video_path": "",
        "status": status,
        "error": "",
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
    }


def get_video(video_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return _row_to_dict(row)


def list_videos(
    channel_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if channel_id is not None:
        clauses.append("channel_id = ?")
        params.append(channel_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with _get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM videos{where} ORDER BY created_at DESC",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def update_video(video_id: int, **fields) -> Optional[dict]:
    if not fields:
        return get_video(video_id)
    if "status" in fields and fields["status"] not in VIDEO_STATUSES:
        raise ValueError(f"invalid status: {fields['status']}")
    fields = _serialize_json_fields(fields)
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [video_id]
    with _get_conn() as conn:
        conn.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", values)
    return get_video(video_id)


def update_status(
    video_id: int,
    status: str,
    error: str = "",
    video_path: str = "",
) -> Optional[dict]:
    """Convenience helper. Clears `error` on any non-failed transition."""
    updates: dict = {"status": status}
    updates["error"] = error if status == VIDEO_STATUS_FAILED else ""
    if video_path:
        updates["video_path"] = video_path
    return update_video(video_id, **updates)


def delete_video(video_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        return cursor.rowcount > 0
