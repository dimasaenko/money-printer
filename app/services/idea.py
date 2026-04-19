import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.services import llm
from app.utils import utils

_DB_PATH = os.path.join(utils.storage_dir("data", create=True), "channels.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    seed_prompt TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute(_SCHEMA)
    logger.info(f"ideas table initialized at {_DB_PATH}")


def save_idea(channel_id: int, title: str, description: str = "", seed_prompt: str = "") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO ideas (channel_id, title, description, seed_prompt, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (channel_id, title, description, seed_prompt, now),
        )
        idea_id = cursor.lastrowid
    return {
        "id": idea_id,
        "channel_id": channel_id,
        "title": title,
        "description": description,
        "seed_prompt": seed_prompt,
        "created_at": now,
    }


def list_saved_ideas(channel_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ideas WHERE channel_id = ? ORDER BY created_at DESC",
            (channel_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_idea(idea_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return dict(row) if row else None


def delete_idea(idea_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        return cursor.rowcount > 0


_KEYWORD_SPLIT_RE = re.compile(
    r"\s*(TITLE\s*:|DESCRIPTION\s*:)\s*",
    re.IGNORECASE,
)


def _strip_markdown_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _clean_idea_text(s: str) -> str:
    s = s.strip().strip('"').strip("'").strip()
    s = re.sub(r"^[\d]+\s*[.)]\s*", "", s)
    s = re.sub(r"^[-*•]\s*", "", s)
    # trailing list-item markers leak in when the next idea starts with "1. TITLE:"
    s = re.sub(r"\s*\n?\s*[\d]+\s*[.)]\s*$", "", s)
    s = re.sub(r"\s*\n?\s*[-*•]\s*$", "", s)
    return s.strip()


def _parse_title_desc(text: str) -> list[dict]:
    # Split on TITLE:/DESCRIPTION: keywords regardless of surrounding whitespace —
    # LLMs often emit the fields on a single line with no newlines between them.
    tokens = _KEYWORD_SPLIT_RE.split(text)
    ideas: list[dict] = []
    current: dict = {}
    i = 1  # tokens[0] is whatever precedes the first keyword
    while i + 1 < len(tokens):
        key = tokens[i].rstrip(":").strip().upper()
        value = _clean_idea_text(tokens[i + 1])
        if key == "TITLE":
            if current.get("title"):
                ideas.append(current)
                current = {}
            current["title"] = value
        elif key == "DESCRIPTION":
            current["description"] = value
        i += 2
    if current.get("title"):
        ideas.append(current)
    return ideas


def _parse_json_ideas(text: str) -> list[dict]:
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        return []
    return [
        {"title": str(p.get("title", "")).strip(), "description": str(p.get("description", "")).strip()}
        for p in parsed
        if isinstance(p, dict) and p.get("title")
    ]


def _parse_ideas_response(response: str, count: int) -> list[dict]:
    text = _strip_markdown_fence(response)

    ideas = _parse_title_desc(text)
    if ideas:
        return ideas[:count]

    try:
        ideas = _parse_json_ideas(text)
        if ideas:
            return ideas[:count]
    except json.JSONDecodeError:
        pass

    return []


def generate_ideas(channel: dict, topic_hint: str = "", count: int = 3) -> list[dict]:
    """Generate video ideas tailored to a channel profile using the configured LLM."""

    content_notes_text = ""
    if channel.get("content_notes"):
        notes = channel["content_notes"]
        if isinstance(notes, list):
            content_notes_text = "\n".join(f"- {n}" for n in notes)
        else:
            content_notes_text = str(notes)

    language = channel.get("language", "en")
    prompt = f"""You are a YouTube content strategist. Produce exactly {count} video ideas for this channel.

Channel: {channel.get('name', '')}
Niche: {channel.get('niche', '')}
Target audience: {channel.get('target_audience', '')}
Tone: {channel.get('tone', '')}
Language: {language}
Video length: {channel.get('video_length_preset', 'medium')}
"""

    if content_notes_text:
        prompt += f"\nContent guidelines:\n{content_notes_text}\n"

    if topic_hint:
        prompt += f"\nTopic hint from user: {topic_hint}\n"

    prompt += f"""
Respond in this EXACT plain-text format. Separate ideas with one blank line.
Do NOT use JSON, markdown, code fences, numbering, or any wrapper.

TITLE: <short catchy title>
DESCRIPTION: <1-2 sentence summary>

TITLE: <short catchy title>
DESCRIPTION: <1-2 sentence summary>

Write titles and descriptions in language: {language}. Produce exactly {count} ideas.
"""

    response = ""
    try:
        response = llm._generate_response(prompt)
        ideas = _parse_ideas_response(response, count)
        if ideas:
            return ideas
        logger.warning(f"ideas response did not parse into any ideas; raw response:\n{response}")
    except Exception as e:
        logger.warning(f"failed to generate ideas: {e}")

    return [{"title": "Generated idea", "description": response}]
