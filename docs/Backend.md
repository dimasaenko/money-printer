# Backend

The backend is a **FastAPI app** with a **services layer** that is also imported directly by the Streamlit WebUI. Both entry points share the same `app/services/*` modules — see [`docs/Frontend.md`](Frontend.md) for the WebUI side.

## Entry points

| File | Role |
|---|---|
| `main.py` | Uvicorn launcher. Reads `config.listen_host`/`listen_port` and runs `app.asgi:app`. |
| `app/asgi.py` | FastAPI app factory. Registers CORS, exception handlers, static mounts (`/tasks` → `storage/tasks`, `/` → `public/`), and startup/shutdown hooks. On startup it calls `channel_service.init_db()` to ensure the SQLite schema exists. |
| `app/router.py` | Root `APIRouter`. Mounts v1 sub-routers: `video`, `llm`, `channel`. |

## Request lifecycle

```
HTTP request
  → uvicorn (main.py)
  → FastAPI app (app/asgi.py)
  → root router (app/router.py)
  → controllers/v1/*.py  (thin — validation + response envelope)
  → services/*.py        (business logic — the real code)
  → state (MemoryState | RedisState) + filesystem (storage/tasks/{task_id})
```

Controllers are deliberately thin: they validate input via Pydantic models (`app/models/schema.py`), dispatch to a service function, and wrap the result with `utils.get_response(status, data, message)`. Errors raise `HttpException` from `app/models/exception.py`, which the global handler at `asgi.py:18` converts to a structured JSON envelope.

## Controllers (app/controllers/v1/)

- `video.py` — Task CRUD, file upload/download/stream endpoints. Owns the `task_manager` (line 48): picks `RedisTaskManager` or `InMemoryTaskManager` based on `config.app["enable_redis"]`. Endpoints: `POST /videos`, `POST /subtitle`, `POST /audio`, `GET /tasks`, `GET /tasks/{task_id}`, `DELETE /tasks/{task_id}`, `GET/POST /bgms`, `GET/POST /musics`, `GET /stream/{path}`, `GET /download/{path}`. The upload handlers defend against path traversal via `_sanitize_upload_filename` and `_resolve_path_within_directory`.
- `llm.py` — `POST /scripts` and `POST /terms` — synchronous LLM calls.
- `channel.py` — Channel profile CRUD (`POST|GET /channels`, `GET|PUT|DELETE /channels/{id}`) and idea generation (`POST /channels/{id}/ideas`). Uniqueness enforced on `slug`. Returns 400 on duplicate slug, 404 on missing channel.

## Services (app/services/)

The services layer is the heart of the app. Each service is a module of plain functions (no classes for the pipeline — classes only where useful, e.g. state).

| Module | Responsibility |
|---|---|
| `task.py` | Orchestrates the full pipeline. Public entry: `start(task_id, params, stop_at="video")`. Progress is reported via `state.update_task(...)` at 5% → 10% → 20% → 30% → ... → 100%. `stop_at` can short-circuit at `script`, `terms`, `audio`, or `subtitle` for partial runs (used by `/scripts`, `/audio`, `/subtitle` endpoints). |
| `llm.py` | Unified LLM interface for 13+ providers. Provider selected via `config.app["llm_provider"]`. Public: `generate_script()`, `generate_terms()`, internal `_generate_response()`. |
| `voice.py` | TTS synthesis (edge-tts, Azure, OpenAI, SiliconFlow) and the `SubMaker` object used to build SRT subtitles from edge-tts word boundaries. |
| `video.py` | MoviePy/FFmpeg composition — concatenation, transitions, subtitle overlay, BGM mixing. |
| `material.py` | Sources video clips from Pexels/Pixabay APIs with key rotation and fallback. |
| `subtitle.py` | Speech-to-text fallback when TTS subtitles aren't available — uses faster-whisper. |
| `state.py` | `BaseState` interface + `MemoryState` (dict-backed) and `RedisState` implementations. The module-level `state` singleton at line 152 is chosen at import time based on `config.app["enable_redis"]`. |
| `channel.py` | Channel profile persistence in SQLite (`storage/data/channels.db`). Dict-based CRUD; JSON fields (`content_notes`, `voice_config`, `music_config`, `video_source_config`, `youtube_config`) are auto-serialized/parsed via `_JSON_FIELDS`. **Known quirk:** `create_channel` returns `None` because `get_channel(lastrowid)` runs before the `with conn:` block commits — rows persist correctly, but re-read via `get_channel_by_slug` / `get_channel` after the call returns. |
| `idea.py` | Two concerns in one module: (1) LLM-driven idea generation — `generate_ideas(channel, topic_hint="", count=3)` returns a list of `{title, description}` dicts by prompting the configured LLM. The prompt asks for a plain-text `TITLE:` / `DESCRIPTION:` format (blank line between ideas, no JSON/markdown/numbering) — chosen over JSON because LLMs frequently produce invalid JSON with unescaped inner quotes (e.g. `"слово "в кавычках"."`). `_parse_ideas_response` tries the plain-text format first, falls back to JSON parsing, then to a single-item fallback with the raw response. (2) SQLite persistence in the same `channels.db` file — `ideas` table with `save_idea(channel_id, title, description, seed_prompt)`, `list_saved_ideas(channel_id)`, `get_idea(id)`, `delete_idea(id)`. `save_idea` returns the data it inserted directly (no re-read), sidestepping the commit-timing quirk that bites `channel.create_channel`. Both `init_db()` calls (channel + idea) run from `app/asgi.py` startup and from the top of `webui/Main.py`. |
| `upload_post.py` | Upload finished videos to external platforms (used by `task.py` post-pipeline). |

## Task manager vs. state

These are two different abstractions — easy to confuse:

- **`app/services/state.py`** — task *state/progress* storage. `update_task(task_id, state=..., progress=..., **fields)` is called from inside the pipeline to report progress. Memory or Redis backed. Read by `GET /tasks/{task_id}`.
- **`app/controllers/manager/`** — task *queue* / concurrency control. `InMemoryTaskManager` or `RedisTaskManager` limits how many pipelines run at once (`max_concurrent_tasks`, default 5). Controllers submit to the manager, which calls `task.start()` in a worker.

## Configuration (app/config/config.py)

- `config.toml` is auto-created from `config.example.toml` on first run.
- Module-level globals are populated at import: `app`, `whisper`, `proxy`, `azure`, `siliconflow`, `ui`, `log_level`, `listen_host`, `listen_port`, `project_version`, etc.
- Env var overrides applied at import: `MPT_APP_REDIS_HOST` or `REDIS_HOST` wins over `config.toml`.
- `CORS_ALLOWED_ORIGINS` is read in `app/asgi.py:56` (comma-separated; defaults to `*`).
- `imagemagick_path` and `ffmpeg_path` from config are exported as `IMAGEMAGICK_BINARY` / `IMAGEIO_FFMPEG_EXE` env vars for MoviePy.
- `save_config()` writes back `[app]`, `[azure]`, `[siliconflow]`, `[ui]` — other sections are preserved but not actively serialized. The WebUI calls this on every rerun.

## Models (app/models/)

- `schema.py` — Pydantic models for requests/responses. Central type: `VideoParams` (line 58) — controls every knob of the video pipeline.
- `const.py` — Task state ints: `FAILED=-1`, `COMPLETE=1`, `PROCESSING=4`. File type allowlists for uploads.
- `exception.py` — `HttpException(task_id, status_code, message, data)` — raise from anywhere in controllers or services to produce a structured error response.

## Storage layout

- `storage/tasks/{task_id}/` — per-task working directory: `script.json`, TTS audio, subtitle SRTs, intermediate clips, final `final-*.mp4`. Mounted at `/tasks` for static serving.
- `storage/data/channels.db` — SQLite DB holding both `channels` and `ideas` tables. Created lazily at startup via `channel_service.init_db()` + `idea_service.init_db()` (same file, two schemas).
- `public/` — served at `/` (docs/assets).

### `ideas` table

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `channel_id` | INTEGER NOT NULL | FK-ish reference to `channels.id` (no FK constraint yet — `PRAGMA foreign_keys` not enabled). |
| `title` | TEXT NOT NULL | |
| `description` | TEXT NOT NULL `''` | |
| `seed_prompt` | TEXT NOT NULL `''` | The optional topic hint the user typed before generation; shown under saved ideas in the UI. |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |

Deleting a channel does **not** cascade-delete its ideas. If that becomes an issue, enable `PRAGMA foreign_keys = ON` in `_get_conn` and add `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE`.

## Key patterns

- **Provider strategy pattern.** LLM, TTS, and material services dispatch on `config.app["<kind>_provider"]` and read provider-specific keys (`openai_api_key`, `pexels_api_keys`, etc.). Adding a provider = add a branch + config block.
- **Services imported both by FastAPI and Streamlit.** Never couple business logic to `fastapi.Request` — keep services framework-agnostic so the WebUI can import them directly (it does; see `webui/Main.py:1081`).
- **Global singletons at import time.** `state`, `task_manager`, config globals are selected once when modules load. Changing config at runtime won't rebuild them.
- **loguru throughout.** Level configured in `config.toml`. The WebUI attaches an extra sink to stream logs into the page.

## Testing

Tests live in `test/` and use `unittest`. Service tests are in `test/services/`. No pytest, no fixtures framework — just plain `TestCase` classes.

```bash
python -m unittest discover -s test                        # all
python -m unittest test/services/test_video.py             # one file
python -m unittest test.services.test_video.TestVideoService.test_preprocess_video  # one method
```
