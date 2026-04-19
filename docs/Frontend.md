# Frontend

The WebUI is a **single-file Streamlit app** at `webui/Main.py` (~1100 lines). There is no React/Vue frontend.

## Important: not a client of the FastAPI server

The WebUI does **not** make HTTP calls to the API. It imports `app.services` modules directly and runs the pipeline in-process:

```python
# webui/Main.py:1081
result = tm.start(task_id=task_id, params=params)
```

The FastAPI server (`main.py` / `app/asgi.py`) and the WebUI are **parallel entry points** sharing the same services layer, not a client/server pair. This means:

- Starting the Streamlit app does not require the FastAPI server to be running.
- The two entry points run the same code, so changes to `app/services/*.py` affect both.
- The Streamlit process must be able to import the whole `app/` package (handled by a `sys.path` hack at `webui/Main.py:10-14`).

## Layout

Top-to-bottom flow (global → channel → per-video → action):

| Section | Content |
|---|---|
| Top row | Title + language selector |
| Basic Settings (expander) | 3 columns: log toggles / LLM provider config / Pexels+Pixabay API keys. **Global-ish settings first, before anything channel-specific.** |
| **Channel selector + info** | Dropdown of active channels, collapsible profile card |
| **Video Ideas panel** *(only when a channel is selected)* | Seed-prompt input + Generate button, transient "new" ideas with per-row Save, saved-ideas list with per-row Use / Delete |
| Main 3-panel layout | Left / Middle / Right panels (see below) — per-video overrides |
| Generate button | Primary CTA — triggers `tm.start()` |

**Main panels** (`panel = st.columns(3)` at line 485):

- **Left panel** (line 493): video subject input, script language, "Generate Video Script and Keywords" button (calls `llm.generate_script` + `llm.generate_terms` synchronously), editable script and terms text areas.
- **Middle panel** (line 554): video concat mode, aspect ratio, clip duration, video count.
- **Right panel** (line 874): subtitle + font settings, plus a nested "API Key management" expander (line 943) for Pexels/Pixabay keys.

## State

- **Session state** (`st.session_state`, initialized near the top of `Main.py`): `video_subject`, `video_script`, `video_terms`, `ui_language`, `local_video_materials`, `selected_channel_id`, `channel_ideas`. Persists across reruns within a session.
- **Config coupling:** Most UI widgets directly mutate the shared `config.app` / `config.ui` dicts from `app/config/config.py`. `config.save_config()` at the end of each script run persists changes back to `config.toml`. Selecting an LLM provider in the UI therefore rewrites `config.toml`.
- **Local materials memo:** `st.session_state["local_video_materials"]` remembers the most recently uploaded local video files so that re-generating with only script changes doesn't drop the materials list.
- **Channel ideas memo:** `st.session_state["channel_ideas"]` holds the last batch of ideas returned by `idea_service.generate_ideas` for the currently selected channel, so the user can pick one without re-calling the LLM. Cleared when the channel changes or a "Use" idea button is clicked (the idea title becomes `video_subject` and the existing `video_script`/`video_terms` are reset).

## i18n

Translation JSONs live in `webui/i18n/` (`en.json`, `zh.json`, `ru.json`, `de.json`, `pt.json`, `tr.json`, `vi.json`). The `tr(key)` helper at `webui/Main.py:201` looks up keys in the currently selected locale; unknown keys fall through to the raw key string, so missing translations degrade gracefully.

## Running the pipeline

1. User clicks **Generate Video** (line 1007) → a new `task_id` is generated.
2. A loguru sink is added that mirrors log records into a `st.code` block for a live log view (line 1067, gated by `config.ui["hide_log"]`).
3. `tm.start(task_id=task_id, params=params)` runs the full pipeline synchronously in the Streamlit process (line 1081).
4. On success, resulting MP4s are rendered via `st.video` (line 1094) and the task folder is opened via `open_task_folder` (Darwin/Windows only).

Because this call is synchronous, the Streamlit UI blocks until the video finishes. The FastAPI `/api/v1/video` endpoint, by contrast, runs the same `tm.start` asynchronously and returns a `task_id` immediately.

## Channel integration

A channel selector sits right after Basic Settings. It reads from `app/services/channel.py` (active channels only) and exposes:

- **Dropdown** — pick a channel or leave as "— No channel —". The selected `id` is held in `st.session_state["selected_channel_id"]`; changing it clears any stale idea cache.
- **Profile card** — collapsible expander showing `niche`, `target_audience`, `tone`, `language`, `video_length_preset`, `content_notes`, and the three JSON configs (`voice_config`, `music_config`, `video_source_config`). Purely informational — the main panels still own the actual pipeline params.

Both `channel_service.init_db()` and `idea_service.init_db()` run unconditionally at the top of `Main.py` — the WebUI does not depend on the FastAPI startup hook.

## Video Ideas panel

Rendered **only when a channel is selected** (hidden otherwise). It sits between the channel card and the main 3-panel layout.

- **Seed prompt** (`st.text_input`, persisted in `st.session_state["idea_seed"]`) — optional topic hint passed to `idea_service.generate_ideas` as `topic_hint`. Empty seed = purely channel-driven.
- **Generate Ideas** button — calls `idea_service.generate_ideas(channel, topic_hint=seed, count=3)`. Results are cached in `st.session_state["channel_ideas"]` as "new" (transient, unsaved) ideas.
- **New ideas list** — rendered as a 3-column grid (`Title` / `Description` / Save button). Save calls `idea_service.save_idea(channel_id, title, description, seed_prompt)`, which inserts into the `ideas` SQLite table. The row is removed from `channel_ideas` on save (to avoid showing it in both lists).
- **Saved ideas list** — read from `idea_service.list_saved_ideas(channel_id)` on every render. Rendered as a 4-column grid (`Title` / `Description` / Use / Delete):
  - **Use** — copies `title` into `video_subject`, resets `video_script`/`video_terms`, so the user can re-run the Left panel's "Generate Video Script and Keywords".
  - **Delete** — calls `idea_service.delete_idea(idea_id)` and reruns.
- Saved ideas with a `seed_prompt` show a caption (`↳ seed text`) beneath the description so the user can see what prompt produced the idea.

## Known gaps

- **Channel fields do not auto-fill the main panels.** Language, voice, bgm volume, video source provider, and orientation on the selected channel are shown for reference only — the user still has to match them in the Settings expander / main panels manually. A future iteration could push these as defaults when a channel is selected.
- **No channel-management UI.** Creating, editing, and deleting channels is still API-only (or via the `/create-channel` slash command).
- **No `/api/v1/ideas` endpoints yet.** Idea CRUD is Python-only (direct calls from `webui/Main.py`); if an external client needs ideas, the `app/controllers/v1/channel.py` or a new controller module would need to expose them.
