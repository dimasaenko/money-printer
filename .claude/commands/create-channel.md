Walk the user through creating a new YouTube channel profile by asking questions one at a time. After gathering all answers, call the MoneyPrinterTurbo API to create the channel.

Ask these questions in order, waiting for each answer before proceeding. Show the field name and a brief explanation. If the user skips a question (says "skip" or just presses enter), use the default value shown.

**IMPORTANT:** For every question after the channel name, proactively propose a concrete suggestion inferred from the channel name and previous answers. The user can accept your suggestion (e.g. "yes", "ok", enter) or override it. This applies to all text fields, sub-questions, and even list items (content notes, voice ID, music style, etc.). Do not just list the generic default — tailor the suggestion to this specific channel. Detect the user's language from the channel name and propose answers in the same language where applicable (e.g. tone, audience descriptions).

**GROUP QUESTIONS IN BATCHES OF 3.** After the channel name (Q1) and slug (Q2, which are tightly coupled and asked together), group the remaining questions in batches of 3. For each batch:

- Use a clear visual separator (e.g. `───` or markdown `---`) between questions within a batch
- Number each question within the batch (1, 2, 3)
- Provide a tailored suggestion for each
- At the end of the batch, ask: **"Accept 1, 2, 3? (or say which to change)"**
- The user can reply "yes" / "accept all" / "1, 3" / "change 2: ..." / etc.

For sub-questions within a config block (voice, music, video source), ask all sub-questions of that block together as one batch (they're naturally 3 sub-questions each).

For the **content notes** question, keep the existing format: propose 3–5 numbered guardrails and let the user accept/edit/remove/add individually — this is a list-building step, not a batch.

1. **Channel name** — Human-readable name (e.g. "Facts About Animals")
2. **Slug** — URL-friendly identifier, auto-suggest based on name (e.g. "facts-about-animals"). Ask user to confirm or change.
3. **Niche** — What the channel is about. Be specific. Propose a niche description based on the channel name. (e.g. "Surprising animal facts & behaviors — short, shareable facts about unusual or surprising animal behaviors, adaptations, and trivia.")
4. **Target audience** — Who watches? Age range, interests. Propose a plausible audience based on niche. (e.g. "Families & kids (7-14); kid-friendly phrasing and content choices.")
5. **Tone** — How should the narration feel? Propose a tone that fits the niche and audience. (e.g. "Fun, punchy, surprising. Energetic narration with emphasis on the 'wow' factor.") Default: ""
6. **Content notes** — Guidelines for the LLM when generating scripts. Propose 3–5 tailored guardrails for this specific niche (e.g. for a mental-health channel: "No medical diagnoses", "Avoid triggering content", "Cite credible sources"). Present them as a numbered list and ask the user to accept, edit, or add more. Default: []
7. **Language** — Language code (e.g. "en", "zh", "es"). Infer from the channel name language. Default: "en"
8. **Video length preset** — short / medium / long. Suggest based on niche (e.g. "short" for quick facts, "medium" for explainers). Default: "medium"
9. **Voice config** — Ask sub-questions, each with a tailored suggestion:
   - Provider: edge-tts / azure / openai (Default: "edge-tts")
   - Voice ID or name — suggest a specific voice ID that matches the channel's language and tone (e.g. for Russian calm content: "ru-RU-SvetlanaNeural") (Default: null)
   - Speed: 0.5-2.0 — suggest based on tone (Default: 1.0)
10. **Music config** — Ask sub-questions, each with a tailored suggestion:
    - Style description — propose a style matching the channel's tone (e.g. "Calm, ambient, soothing" for mental health) (Default: "")
    - Volume: 0.0-1.0 (Default: 0.2)
    - Source: local / api (Default: "local")
11. **Video source config** — Ask sub-questions:
    - Primary provider: pexels / pixabay (Default: "pexels")
    - Fallback provider: pexels / pixabay / none (Default: "pixabay")
    - Orientation: landscape / portrait (Default: "portrait")

After all questions are answered, show a summary of the channel profile and ask the user to confirm.

On confirmation, use the Bash tool to call the API:
```
curl -s -X POST http://127.0.0.1:8080/api/v1/channels \
  -H "Content-Type: application/json" \
  -d '<the JSON payload>'
```

If the API is not running, alternatively create the channel directly by running a Python script:
```
cd /Users/dmitriysaenko/dev/money-printer/MoneyPrinterTurbo && python -c "
from app.services.channel import init_db, create_channel
init_db()
channel = create_channel({...the data dict...})
print(channel)
"
```

Show the created channel details when done.
