# 2026-04-02 PR Merge and Verification Record

## PRs merged and pushed in this round

- `#837` `fix: update google-generativeai version for response_modalities support`
- `#835` `fix: add missing pydub dependency to requirements.txt`
- `#850` `feat: support reading subtitle position from config file`
- `#838` `feat: add MiniMax as LLM provider`
- `#811` `refactor: optimize codebase for better performance and reliability`
- `#848` `feat: support GPU acceleration for faster-whisper in Docker`
- `#843` `feat: Add Upload-Post integration for cross-posting to TikTok/Instagram`

## Main-branch commits after merging

- TTS and subtitle fix baseline commit: `953a6c0` `fix: restore edge tts synthesis and readable subtitles`
- Current main-branch commit: `1f8a746`

## Verification results at merge time

### Passed

- `#837`
  - Imports correctly after the dependency upgrade
  - `google-generativeai==0.8.6` is in effect
- `#835`
  - `pydub==0.25.1` is in effect
- `#850`
  - `subtitle_position` and `custom_position` can be read from the configuration file
- `#838`
  - MiniMax provider wiring is functional
  - Verified `_generate_response` using a mocked call
- `#811`
  - Main branch imports correctly
  - Sampled unit tests pass
- `#848`
  - `docker compose -f docker-compose.yml -f docker-compose.gpu.yml config` parses correctly
- `#843`
  - Upload-Post service imports and mocked upload call both pass
  - When layered with earlier PRs there was only a configuration section conflict in `config.example.toml`; manually preserved content from both sides

### Rejected and closed

- `#852`
  - Restores audio but breaks the subtitle pipeline and removes Gemini logic still called from the WebUI
- `#787`
  - Does not resolve the current `403` scenario
- `#841`
  - Conflicts with the current main-branch TTS/subtitle fixes; its benefits are already covered by smaller PRs
- `#824`
  - The ModelsLab path can produce audio but its subtitle pipeline fails, so a usable SRT cannot be produced
- `#840`
  - Adds `video_source="ai"` on the backend, but the WebUI does not yet support that value, so end-to-end is unusable
- `#826`
  - Conflicts with the current main-branch `voice.py` and its dependency changes; did not pass merge verification
- `#751`
- `#749`
- `#742`
- `#705`
  - The four PRs above are all `DIRTY` against the current main branch and did not pass merge verification

## Smoke test record

### Service restart

- API: `http://127.0.0.1:8080/docs`
- WebUI: `http://127.0.0.1:8501`

### First full video task

- Task ID: `ced0b190-dd72-489c-b978-2761740933db`
- Result: failed
- Conclusion:
  - The API defaults `video_transition_mode=null`
  - The video concatenation stage in `app/services/video.py` accesses `video_transition_mode.value` directly
  - This caused the task thread to exit abnormally, leaving the task status at `state=4, progress=75`

### Second full video task

- Task ID: `8b2a0e6e-b3e6-44ab-a1b4-1865a0b4788d`
- Submission:
  - `POST /api/v1/videos`
  - Used the local asset `/Users/harry/Projects/Python/MoneyPrinterTurbo/test/resources/1.png`
  - Explicitly specified `video_transition_mode="FadeIn"`
- Result: succeeded
- Task status: `state=1, progress=100`

### Outputs from the second task

- Audio: `/Users/harry/Projects/Python/MoneyPrinterTurbo/storage/tasks/8b2a0e6e-b3e6-44ab-a1b4-1865a0b4788d/audio.mp3`
  - Duration: `8.952s`
  - Size: `53712 bytes`
- Concatenated video: `/Users/harry/Projects/Python/MoneyPrinterTurbo/storage/tasks/8b2a0e6e-b3e6-44ab-a1b4-1865a0b4788d/combined-1.mp4`
  - Duration: `9.000s`
  - Size: `177666 bytes`
- Final video: `/Users/harry/Projects/Python/MoneyPrinterTurbo/storage/tasks/8b2a0e6e-b3e6-44ab-a1b4-1865a0b4788d/final-1.mp4`
  - Duration: `9.000s`
  - Size: `352810 bytes`
- Subtitle: `/Users/harry/Projects/Python/MoneyPrinterTurbo/storage/tasks/8b2a0e6e-b3e6-44ab-a1b4-1865a0b4788d/subtitle.srt`

### Subtitle sample from the second task

```srt
1
00:00:00,100 --> 00:00:03,300
This is a complete smoke test after merging into the main branch

2
00:00:03,875 --> 00:00:05,350
We need to confirm the audio

3
00:00:05,575 --> 00:00:08,375
Subtitles and the final video can all be generated correctly
```

## Remaining risks to watch

- `#843` has only been verified with mocks and has not yet been tested end-to-end with a real Upload-Post API key
- `#848` has only been verified by parsing the Docker GPU configuration; it has not been run on a real GPU environment
- When the API defaults `video_transition_mode=null`, the full video task still has a regression risk
