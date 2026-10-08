# AI English Conversation Tutor — Complete Project Documentation

This document describes the repository as inspected on 2026-10-07. Statements
about behavior are based on the checked-in source files, not solely on the
README. Environment-specific settings, locally installed models, and contents
of ignored runtime files can differ from the checked-in example configuration.
No credentials or local database contents are reproduced here.

## 1. Project Title

**AI English Conversation Tutor**

The browser interface brands the application **English Bee**.

## 2. Project Overview

This is a locally runnable English conversation practice application. A user
can type a message or record a spoken message in the browser. The FastAPI
backend obtains an LLM reply and any grammar corrections, returns pronunciation
transcriptions using IPA resources where available, calculates a speech
recognizer confidence summary when word probabilities are supplied, and saves
the conversation turn and corrections in SQLite.

The application also has a review mode, a weakness/statistics dashboard, an
end-of-session summary, and speech playback. It is a single-page browser
interface in `static/index.html`; there is no separate frontend build system.

## 3. Problem Statement

English learners benefit from frequent practice, understandable feedback, and
the ability to revisit mistakes. A conventional text-only chat does not itself
provide microphone recording, speech transcription, reusable correction
history, spaced review, or spoken playback in one workflow.

This project combines those learning activities in a small browser application.
Its displayed ASR confidence is explicitly a transcription-model confidence,
not a measurement of pronunciation quality.

## 4. Objectives

- Enable short English conversations through text or recorded speech.
- Ask an LLM for concise English replies and structured grammar corrections.
- Offer an optional more-natural expression for the user's sentence.
- Persist turns and corrections in a local SQLite database.
- Present correction statistics and recent ASR confidence values.
- Let learners review stored corrections and schedule later reviews.
- Provide server-side and browser-side speech playback choices/fallback.
- Make the provider and local speech-recognition settings configurable.

## 5. Target Users

- English learners who want to practice short written or spoken exchanges.
- Students preparing or presenting a software project.
- Individual developers evaluating local LLM and speech workflows.

The source does not implement user accounts, roles, or per-user authorization.
The target is therefore best understood as an individual/local learning tool,
not a multi-tenant service.

## 6. Main Features

**Implemented in source code:**

- Text chat through `POST /api/chat`.
- Microphone recording using browser `getUserMedia` and `MediaRecorder`.
- Server-side transcription through local `faster-whisper` or optional OpenAI
  transcription.
- Prompt-based grammar feedback and natural-expression suggestions.
- Error-type tagging using explanation keywords and word-diff heuristics.
- SQLite persistence of sessions, turns, corrections, and review schedule.
- Review queue with exact/near-match answer judgement and simple SRS intervals.
- Dashboard counts, error categories, examples, and ASR confidence trends.
- Session summary with rule-based statistics and optional LLM feedback.
- IPA text generation through `eng_to_ipa` and/or an NLTK CMU dictionary.
- Server-side Edge TTS or OpenAI TTS and a browser SpeechSynthesis fallback.
- Local HTTPS certificate generation for development when starting the server.

**Clarification:** The UI and API field names retain some historical
`pronunciation_score` terminology. The current scoring path calculates
recognition confidence and does not assess phoneme accuracy, accent, rhythm, or
intelligibility.

## 7. Technology Stack

| Area | Technology verified in source |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Frontend | HTML, CSS, vanilla JavaScript in `static/index.html` |
| Persistence | SQLite through Python's standard-library `sqlite3` |
| LLM | Ollama local HTTP API; optional OpenAI and Anthropic HTTP APIs |
| Speech-to-text | `faster-whisper` locally; optional OpenAI Audio Transcriptions API |
| Text-to-speech | `edge-tts`; optional OpenAI Audio Speech API; browser Web Speech API fallback |
| Pronunciation text | `eng_to_ipa`, NLTK `cmudict`, local ARPAbet-to-IPA mapping |
| TLS certificate generation | `cryptography` |
| HTTP clients | `httpx` |
| Tests | `pytest`-style tests and a direct-run FastAPI `TestClient` script |

## 8. Complete System Architecture

The browser makes same-origin HTTP requests to the FastAPI app. FastAPI serves
the HTML page and the `/static` assets, accepts JSON or multipart requests,
calls the selected provider, delegates storage and query work to `db.py`, and
returns JSON or MP3 audio.

The principal source modules are:

- `static/index.html`: page markup, styling, interface state, browser
  microphone, fetch requests, rendering, and browser TTS fallback.
- `server.py`: FastAPI app, routes, provider adapters, prompts, audio handling,
  IPA generation, summary builders, and TLS startup helpers.
- `config.py`: `.env` loading and provider/application settings.
- `db.py`: SQLite schema creation/migration and persistence/query operations.
- `error_tagger.py`: rule-based correction type assignment.
- `review_logic.py`: normalized string comparison for review answers.

### Important Module Profiles

#### `config.py`

**Purpose:** Load and expose provider and application settings.  
**File:** `config.py`.  
**Function(s):** `load_local_env`.  
**Input:** OS environment variables and optional `.env` lines.  
**Processing:** Uses `setdefault` so existing OS variables take precedence;
defines provider defaults and `SYSTEM_PROMPT`.  
**Output:** Module-level configuration values.  
**Dependencies:** Python `os` and `pathlib`.  
**How it connects with other modules:** Imported by `server.py` and `db.py`.  
**Simple explanation:** One place provides settings to the rest of the app.  
**Viva explanation:** Configuration is loaded once at import time and exposed
as module constants; some server settings are fixed in code rather than
environment variables.

#### `db.py`

**Purpose:** Persist and query conversation and learning records.  
**File:** `db.py`.  
**Function(s):** `get_connection`, `init_db`, `save_turn`, `get_history`,
`get_session_summary_data`, `get_recent_sessions`, `get_all_corrections`,
`get_error_stats`, `get_dashboard_stats`, `get_due_reviews`,
`get_correction`, `record_review_result`.  
**Input:** Session IDs, turns, correction dictionaries, limits, and review
answers/results.  
**Processing:** Executes SQLite statements, applies schema migrations,
normalizes query results, and commits/rolls back transactions.  
**Output:** Stored rows or Python dictionaries/lists for the API.  
**Dependencies:** `sqlite3`, standard-library time/path/context helpers, and
`error_tagger.tag_correction`.  
**How it connects with other modules:** Called by routes in `server.py`; tests
replace `DB_PATH` with a temporary file.  
**Simple explanation:** It saves and retrieves the learner's progress.  
**Viva explanation:** A connection context manager enables foreign keys,
commits successful work, rolls back failures, and closes connections.

#### `error_tagger.py`

**Purpose:** Assign a coarse category to each saved correction.  
**File:** `error_tagger.py`.  
**Function(s):** `tag_correction`, `_diff_heuristic`, `_tokenize`,
`_is_tense_pair`, `_is_plural_pair`.  
**Input:** Original text, corrected text, and LLM explanation.  
**Processing:** Checks configured explanation keyword patterns in priority
order, then applies a limited token diff.  
**Output:** One of `tense`, `article`, `preposition`, `word_order`,
`subject_verb`, `plural`, `vocabulary`, `spelling`, or `other`.  
**Dependencies:** Python `re` and `difflib`.  
**How it connects with other modules:** `db.save_turn()` calls it before
inserting correction rows.  
**Simple explanation:** It labels common types of mistakes without another
AI call.  
**Viva explanation:** This is a heuristic classifier; it is separate from and
less comprehensive than LLM-generated correction content.

#### `review_logic.py`

**Purpose:** Compare a review answer with the stored correction.  
**File:** `review_logic.py`.  
**Function(s):** `normalize_review_text`, `judge_review_answer`.  
**Input:** Learner answer and stored corrected sentence.  
**Processing:** Lowercases, trims, compresses whitespace, ignores trailing
punctuation, checks exact equality, then calculates a
`difflib.SequenceMatcher` ratio.  
**Output:** A dictionary containing `correct`, `close`, and `ratio`.  
**Dependencies:** Python `difflib` and `re`; no LLM.  
**How it connects with other modules:** `server.review_answer` invokes it and
then updates SRS state through `db.record_review_result`.  
**Simple explanation:** It checks whether the learner's sentence matches the
target closely enough.  
**Viva explanation:** Exact match is correct; a non-exact ratio of at least
`CLOSE_RATIO_THRESHOLD` (`0.85`) is marked close but remains incorrect for
review scheduling.

#### Speech and pronunciation helpers in `server.py`

**Purpose:** Convert text to IPA, transcribe recordings, calculate available
ASR confidence, and synthesize speech.  
**File:** `server.py`.  
**Function(s):** `get_ipa`, `get_sentence_ipa`, `load_cmu_dict`,
`calculate_speech_recognition_confidence`, `transcribe_audio_faster_whisper`,
`transcribe_audio_openai`, `synthesize_speech_edge`, and
`synthesize_speech_openai`.  
**Input:** English text, audio bytes/files, provider configuration, and model
word probabilities.  
**Processing:** Selects optional libraries/providers, maps pronunciation
symbols, writes temporary audio files for local transcription, and gathers
audio chunks for server TTS.  
**Output:** IPA entries, transcript metadata, confidence summaries, or MP3
bytes.  
**Dependencies:** Optional `eng_to_ipa`, `nltk`, `faster-whisper`,
`edge-tts`; `httpx` for cloud APIs; Python standard library.  
**How it connects with other modules:** Called by `/api/chat`,
`/api/pronunciation`, `/api/transcribe`, and `/api/tts`; frontend calls the
corresponding routes.  
**Simple explanation:** These helpers handle the app's text/audio conversions.  
**Viva explanation:** ASR recognition probabilities describe transcription
confidence; IPA lookup does not compare the recorded audio against a target
pronunciation.

#### Test modules

**Purpose:** Exercise selected behavior without depending on a live LLM.  
**File:** `test_speech_confidence.py` and `test_summary.py`.  
**Function(s):** The confidence test functions and summary/parser/API test
functions listed in Section 47.  
**Input:** Fixed sample sentences, word probabilities, temporary SQLite data,
and mocked model responses.  
**Processing:** Assertions validate return values and expected HTTP paths.  
**Output:** Test pass/fail results.  
**Dependencies:** Project modules, FastAPI TestClient, and pytest-style
collection; the summary test can also run directly.  
**How it connects with other modules:** Tests import `server.py` and `db.py`;
the summary test substitutes a temporary `db.DB_PATH` and mocks
`server.get_llm_response`.  
**Simple explanation:** The tests check important code paths with controlled
input.  
**Viva explanation:** Mocking isolates summary endpoint behavior from external
LLM availability; these tests do not establish live provider reliability.

## 9. Architecture Diagram

```text
                         ┌────────────────────────────┐
                         │ User's browser             │
                         │ static/index.html          │
                         │ HTML + CSS + JavaScript    │
                         └─────────────┬──────────────┘
                                       │ HTTPS/HTTP
                 ┌─────────────────────┼───────────────────────┐
                 │                     │                       │
          POST /api/chat      POST /api/transcribe       POST /api/tts
                 │                     │                       │
                 └─────────────────────┼───────────────────────┘
                                       ▼
                         ┌────────────────────────────┐
                         │ server.py / FastAPI        │
                         │ routes, validation, flows │
                         └──────┬───────────┬─────────┘
                                │           │
                 ┌──────────────┘           └────────────────┐
                 ▼                                           ▼
       ┌──────────────────────┐                   ┌─────────────────────┐
       │ config.py            │                   │ db.py               │
       │ provider settings    │                   │ SQLite operations  │
       └──────┬───────────────┘                   └─────────┬───────────┘
              │                                             ▼
     ┌────────┴─────────┐                          ┌─────────────────────┐
     │                  │                          │ tutor.db            │
     ▼                  ▼                          │ sessions/turns/     │
 Ollama / cloud     faster-whisper /                │ corrections         │
 LLM providers      cloud transcription             └─────────────────────┘
              │
              └── edge-tts / OpenAI TTS as selected
                  (browser SpeechSynthesis is fallback)
```

The diagram shows logical paths, not a claim that every provider runs or is
configured in every installation. Local Ollama and local faster-whisper still
require their model files/runtime to be available.

## 10. Complete Project File Structure

This tree lists the repository's tracked project files observed during
inspection. `PROJECT_DOCUMENTATION.md` is the sole file added by this task.
Ignored runtime files such as `.env`, certificates, the generated SQLite
database, caches, and `.venv` are deliberately not listed with their contents.

```text
.
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── config.py
├── db.py
├── docs/
│   └── assets/
│       └── ai-english-conversation-tutor-overview.png
├── error_tagger.py
├── requirements.txt
├── review_logic.py
├── server.py
├── start.bat
├── start.sh
├── static/
│   ├── bee.svg
│   └── index.html
├── test_speech_confidence.py
└── test_summary.py
```

Other relevant paths:

- `tutor.db`: configured runtime database path; ignored by `.gitignore`.
- `.env`: optional local configuration; ignored by `.gitignore`. Its values
  are intentionally not reproduced.
- `cert.pem` and `key.pem`: generated local TLS files; ignored by
  `.gitignore`.
- `.venv/` and `__pycache__/`: local environment/cache, not project source.

## 11. Frontend Explanation

### Frontend

**Purpose:** Provide chat, audio recording, review, statistics, summary, and
playback in one responsive browser page.

**File:** `static/index.html`; icon: `static/bee.svg`.

**Function(s):** `checkHealth`, `startRecording`, `stopRecording`,
`transcribeAndSend`, `sendText`, `submitTurn`, `renderTurn`, `speak`,
`speakWithBrowser`, `openStats`, `openReview`, `submitReviewAnswer`,
`openSummary`, `renderSummary`, and `resetConversation`.

**Input:** Typed text, microphone audio, API JSON responses, and user review
answers.

**Processing:** The page manages state in JavaScript, records audio using
browser media APIs, sends `fetch` requests, renders returned content, and
updates overlays and status indicators.

**Output:** Conversation cards, corrections, suggestions, summary/dashboard
views, status messages, and playback.

**Dependencies:** A modern browser; microphone recording requires browser
support and permission. `getUserMedia` generally requires a secure context such
as HTTPS or localhost.

**How it connects with other modules:** Calls FastAPI routes on the current
origin; does not call Ollama or SQLite directly.

**Simple explanation:** This file contains both the visible page and the
JavaScript that connects it to the backend.

**Viva explanation:** The client is a static single-page application using
vanilla JavaScript and same-origin REST calls; it has no separate framework or
bundler in the checked-in project.

The page includes the main chat, a microphone button, text input, a send button,
a listening mode, a review overlay, a stats overlay, a report overlay, and
dynamic content containers. The document currently declares `lang="ja"` even
though the visible interface text is English; this is metadata in the source,
not proof of a Japanese-language interface.

The `esc` and `escAttr` helpers are used to escape dynamic content in many
rendering contexts. The UI's session identifier is created with
`'session_' + Date.now()` in JavaScript; it is not restored from local storage.

## 12. Backend Explanation

### Backend

**Purpose:** Serve the UI, expose application APIs, orchestrate providers,
compute feedback-related data, and start the local server.

**File:** `server.py`.

**Function(s):** `chat`, `transcribe`, `text_to_speech`, `get_pronunciation`,
`call_ollama`, `call_openai`, `call_anthropic`, `parse_llm_json`,
`calculate_speech_recognition_confidence`, `build_session_summary_stats`,
`generate_self_signed_cert`, and other route/provider helpers.

**Input:** FastAPI request models, uploaded audio, current configuration, and
provider responses.

**Processing:** Selects the configured provider; parses and normalizes
responses; invokes database and pronunciation helpers; emits HTTP errors when
appropriate.

**Output:** HTML, JSON, MP3 audio, and startup diagnostics.

**Dependencies:** `fastapi`, `uvicorn`, `httpx`, `config.py`, `db.py`,
`review_logic.py`, and optional packages such as `faster-whisper`,
`edge-tts`, `eng_to_ipa`, NLTK, and `cryptography`.

**How it connects with other modules:** `config.py` selects providers,
`db.py` stores and reads data, `error_tagger.py` assigns error categories
through `db.save_turn`, and `review_logic.py` compares quiz responses.

**Simple explanation:** FastAPI is the bridge between the browser, AI/speech
providers, and the local database.

**Viva explanation:** `server.py` defines Pydantic request models, asynchronous
REST endpoints, provider adapters, response parsing, and Uvicorn startup.

`FastAPI(title="AI English Conversation Tutor")` is configured with permissive
CORS (`allow_origins=["*"]`, credentials, methods, and headers allowed). Static
assets are mounted at `/static`. The startup event initializes SQLite and
attempts to load the CMU pronunciation dictionary.

## 13. API Endpoints

| Method and route | Input | Source behavior / output |
|---|---|---|
| `GET /` | None | Returns `static/index.html`. |
| `GET /static/...` | Static path | Serves files mounted from `static/`. |
| `POST /api/chat` | JSON `ChatRequest`: `text`, optional/default `session_id`, `confidence`, `words` | Calls LLM, returns reply, corrections, natural expression, IPA, ASR confidence, and persists the turn. |
| `POST /api/transcribe` | Multipart upload field `audio` | Transcribes using selected STT provider; rejects empty audio and files over 25 MiB. |
| `POST /api/pronunciation` | JSON `TTSRequest` (`text`, optional `voice`) | Returns `{"ipa": [...]}` from `get_sentence_ipa`; this route is implemented even though the main chat also returns IPA inline. |
| `POST /api/tts` | JSON `TTSRequest` (`text`, optional `voice`) | Returns MP3 bytes; text must be non-empty and no longer than 1,000 characters. |
| `GET /api/sessions` | Query `limit` (default 20) | Returns recent session summaries from `db.get_recent_sessions`. |
| `GET /api/corrections` | Query `limit` (default 100) | Returns all-session correction history from `db.get_all_corrections`. |
| `GET /api/review/due` | Query `limit` (default 10; clamped to 1–50) | Returns due correction items. |
| `POST /api/review/answer` | JSON `correction_id`, `answer_text` | Checks an answer, records the review, returns judgement and SRS state; 404 if correction is absent. |
| `GET /api/stats` | None | Returns totals, average recognition confidence, per-error counts/examples, and recent scores. |
| `GET /api/summary/{session_id}` | Path session ID | Returns summary statistics and generated LLM feedback, or 404 if there are no turns. |
| `GET /api/health` | None | Returns provider/model names and readiness flags. |
| `GET /api/models` | None | Lists provider models; for Ollama it queries `/api/tags`. |

Provider APIs called by the backend are not application routes. The current
source calls Ollama `/api/chat` and `/api/generate`, OpenAI Chat Completions,
OpenAI Audio Transcriptions, OpenAI Audio Speech, and Anthropic Messages.

## 14. Complete `/api/chat` Flow

1. The browser's `submitTurn` sends JSON to `POST /api/chat`. Text input sets
   `text`, `session_id`, `confidence: 0`, and an empty `words` array. The
   microphone path sends recognized text and any word records returned by
   `faster-whisper`.
2. `ChatRequest` parses the request. `chat` strips `req.text`; an empty result
   returns HTTP 400.
3. `db.get_history(session_id, MAX_CONVERSATION_HISTORY)` retrieves recent
   turns as alternating `user` and `assistant` messages.
4. The handler builds `system` + history + current `user` messages using
   `config.SYSTEM_PROMPT`.
5. `get_llm_response` selects Ollama, OpenAI, or Anthropic based on
   `LLM_PROVIDER`.
6. `parse_llm_json` attempts to extract an object containing `reply` from
   model output. Its fallback treats raw text as the reply when parsing fails.
7. `get_sentence_ipa` is called on the user's text and the LLM reply.
8. `calculate_speech_recognition_confidence(req.words)` averages valid word
   probabilities. If unavailable and a valid `confidence` between 0 and 1 is
   supplied, the handler creates a browser-ASR confidence result. The current
   page sends zero for this field, so its active microphone path uses backend
   word probabilities when present.
9. `db.save_turn` stores the user text, reply, natural expression,
   encouragement, and confidence; it stores correction rows and invokes
   `tag_correction`.
10. The JSON response includes `reply`, `corrections`, `natural_expression`,
    `encouragement`, `user_ipa`, `reply_ipa`, and `pronunciation_score`.
11. The browser renders a conversation card, correction list, optional natural
    expression, and tutor reply. It displays the user's IPA row; the returned
    `reply_ipa` is not rendered by the current `renderTurn` implementation.

## 15. Ollama Integration

`call_ollama(messages)` in `server.py` uses `httpx.AsyncClient` with a
120-second timeout. It first sends a non-streaming request to
`{OLLAMA_BASE_URL}/api/chat`, passing the configured model, messages, and
temperature `0.7`. If the endpoint returns 404, or raises an HTTP status error,
it falls back to `/api/generate`, converting each role/content pair into a
plain prompt. A connection failure is reported as HTTP 503. Other fallback
errors are surfaced as HTTP 500.

Ollama is local by default (`OLLAMA_BASE_URL` defaults to
`http://localhost:11434`). The backend still needs a reachable Ollama service
and the requested model pulled/available. `is_llm_ready()` treats the Ollama
provider as configured; that readiness flag is not a live connection test.
`GET /api/models` performs an actual `/api/tags` query.

## 16. `ornith:9b` Model Explanation

The checked-in `.env.example` currently sets:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=ornith:9b
```

In this application, `ornith:9b` is the Ollama model identifier passed to
Ollama requests and shown in the UI health label. The application repository
does not contain the model weights, model manifest, training information, or
documentation that verifies the model's architecture or capabilities. Those
details are therefore **not confirmed in source code**.

`config.py` has a fallback default of `gemma2:latest`. The effective value is
overridden by an OS environment variable or `.env` value if present; the
checked-in README's local setup example also says `gemma2:latest`, which does
not match the current `.env.example`. Do not assume one value is effective on a
particular machine without checking its environment.

## 17. System Prompt Explanation

`config.SYSTEM_PROMPT` in `config.py` instructs the selected LLM to:

- Act as a strict English grammar tutor and keep replies to 1–2 sentences.
- Check word order, repeated words, articles, prepositions,
  subject-verb agreement, tense, and other grammar.
- Reply naturally in English and ask a follow-up question.
- Return only JSON with `reply`, `corrections`, and `natural_expression`.

The prompt includes examples and asks the model to find all errors. This is an
instruction to the model, not a deterministic guarantee that every model
response will be complete or valid. `parse_llm_json` is a response parser, not
a grammar validator.

The separate `SUMMARY_FEEDBACK_PROMPT` in `server.py` asks for two highlights,
two focus areas, a phrase to remember, and a short closing message. Summary
statistics themselves are calculated in Python.

## 18. Conversation History

`db.get_history` selects recent turns for one `session_id`, orders them by
descending ID, limits them to `max(1, limit // 2)` turns, then reverses the
result to chronological order. Each turn contributes one user and one
assistant message.

`MAX_CONVERSATION_HISTORY` is 20 messages in `config.py`, so the prompt
normally receives at most 10 previous conversation turns plus the current
message and system prompt. `encouragement`, corrections, and natural
expression values are not added to the history messages by `get_history`.

## 19. Session Management

The browser creates a timestamp-based session ID when the page loads and
creates a new one on `resetConversation()`. The ID is sent with chat requests
and used by the summary endpoint.

`db.save_turn` inserts a session row if needed, then inserts its turn and
corrections. The session ID is not stored in browser local storage or recovered
after a reload. The reset button clears the displayed conversation and changes
the client-side ID; it does **not** delete existing records from SQLite.

`GET /api/sessions` lists recent session metadata, but the current UI does not
provide session selection or deletion. No authentication or user-to-session
ownership layer is implemented.

## 20. Speech-to-Text

The UI captures audio, sends it as multipart data to `/api/transcribe`, receives
text, then forwards the text and any returned per-word records to `/api/chat`.
`STT_PROVIDER` selects `faster_whisper`, `openai`, or `disabled`.

The route reads the upload, rejects empty content (400) and content over
25 MiB (413), determines a filename/content type, and dispatches to the
configured implementation. Disabled transcription returns HTTP 503.

## 21. `faster-whisper`

`_transcribe_audio_faster_whisper_file` in `server.py` lazily gets a
`WhisperModel`, requests transcription with:

- `task="transcribe"`
- configured language and beam size
- configured VAD filter
- `condition_on_previous_text=False`
- `word_timestamps=True`

It joins segment text and returns `text`, provider name, language, duration,
and a `words` list containing word, probability, start, and end values. Empty
transcription returns HTTP 422. `transcribe_audio_faster_whisper` writes the
uploaded bytes to a temporary file, executes the synchronous transcription in
`asyncio.to_thread`, and attempts to remove the temporary file in `finally`.

`resolve_faster_whisper_runtime` uses `ctranslate2` to select CUDA/CPU and a
supported compute type when the corresponding settings are `auto`.
`get_faster_whisper_model` caches one loaded model and guards initialization
with a `Lock`.

## 22. Microphone Workflow

The frontend uses `navigator.mediaDevices.getUserMedia` and `MediaRecorder`.
It requests echo cancellation, noise suppression, and auto gain control, then
chooses a supported WebM/Opus or MP4 MIME type. The first microphone-button
press starts recording; the next stops it. Audio chunks become a `Blob`, then
a `FormData` field named `audio`.

The page reports permission, recording, transcription, and failure status in
the recognition preview. It retains an object URL for replaying the user's
recording and revokes the URL when replaced or reset. Unsupported recording
falls back to a prompt to type instead; microphone denial is surfaced to the
user.

## 23. Text-to-Speech

`POST /api/tts` routes text to `edge-tts` or OpenAI based on `TTS_PROVIDER`.
It returns an `audio/mpeg` response. Text must not be blank and must not exceed
`TTS_MAX_TEXT_LENGTH` (1,000 characters).

In the browser, `speak(text)` first requests `/api/tts`, creates an object URL
for the returned audio, and plays it. It stops prior playback, uses a request
counter to ignore stale responses, and revokes object URLs on playback end or
error. If the request or playback fails, it calls `speakWithBrowser`.

## 24. Edge-TTS

`synthesize_speech_edge` imports `edge_tts`, creates
`edge_tts.Communicate(text, voice, rate=EDGE_TTS_RATE)`, collects streamed
audio chunks, joins them, and returns MP3 bytes. The voice is the request's
voice if supplied, otherwise `EDGE_TTS_VOICE`; the rate comes from
configuration.

Although the package is used by the server, Edge TTS is a network-backed
service. Therefore a fully local LLM/STT setup does not make the default speech
generation path offline.

## 25. Browser `SpeechSynthesis` Fallback

`speakWithBrowser` uses the browser's Web Speech API, cancels earlier speech,
sets `lang` to `en-US`, rate to `0.9`, pitch to `1`, and prefers an available
Google English voice, then an `en-US` voice, then any English voice.

It runs when server TTS is unavailable or playback fails. The browser fallback
depends on browser/OS voice availability and is not a bundled speech model.
When the server returns HTTP 503, `ttsAvailable` is set false so subsequent
calls go directly to browser speech for the current page session.

## 26. IPA / Pronunciation System

`get_sentence_ipa` splits text into English word tokens and punctuation,
then calls `get_ipa` for each token. `get_ipa` first tries `eng_to_ipa.convert`
when importable; if that does not return a usable pronunciation, it checks
`cmu_dict`. `load_cmu_dict`, called on startup, attempts to download/load NLTK
`cmudict` and maps ARPAbet phones through `ARPABET_TO_IPA`.

`POST /api/pronunciation` returns this IPA list. `POST /api/chat` also returns
`user_ipa` and `reply_ipa`. The current UI renders an IPA reference row for
`user_ipa`; it does not currently render the returned `reply_ipa`.

This is text-to-IPA lookup, not audio-based pronunciation assessment. The
visible confidence value is ASR model confidence and must not be described as
a pronunciation score.

## 27. Grammar Correction

The primary grammar feedback is generated by the configured LLM according to
`SYSTEM_PROMPT`. A structured correction is expected to contain `original`,
`corrected`, and `explanation`. `parse_llm_json` tolerates Markdown code
fences and surrounding text and falls back to a plain-text reply if it cannot
parse the expected object.

`db.save_turn` calls `error_tagger.tag_correction` for each correction, storing
an `error_type`. The tagger checks explanation keywords in priority order,
then uses limited token-diff heuristics for word order, tense, subject-verb
agreement, articles, prepositions, pluralization, spelling, and vocabulary.
It is a lightweight classifier, not a comprehensive language grammar engine.

## 28. Natural Expression Feature

The system prompt requests `natural_expression`: a more natural version of the
whole sentence, or `null` if the sentence is already natural. The value is
returned by `/api/chat`, saved in `turns`, and shown with a playback button
when present. The session-summary statistics include unique natural
expressions in encounter order.

The suggestion is generated by the LLM; there is no separate phrase-ranking or
linguistic evaluation model in the repository.

## 29. Database Architecture

`db.py` uses Python's built-in `sqlite3`. The database path is
`BASE_DIR / "tutor.db"` by default. `get_connection()` opens a connection,
sets `sqlite3.Row`, enables foreign keys, commits on success, rolls back on an
exception, and closes the connection.

`init_db()` creates tables and indexes and attempts additive `ALTER TABLE`
migrations for older database files. `save_turn()` persists a successful
conversation and its corrections. Database helper functions serve history,
dashboard, review, and summary endpoints.

## 30. Database Tables

### `sessions`

One row per session identifier. Created on demand by `save_turn`.

### `turns`

One row per user/assistant exchange, attached to a session. Contains the
utterance, reply, optional expression/encouragement, time, and confidence
fields.

### `corrections`

Zero or more correction rows per turn. Contains original/corrected text,
explanation, category, and spaced-review state.

## 31. Database Columns

Column definitions below reflect current `CREATE TABLE` statements plus the
additive migration columns in `db.init_db()`.

| Table | Columns |
|---|---|
| `sessions` | `id TEXT PRIMARY KEY`; `created_at TEXT NOT NULL` |
| `turns` | `id INTEGER PRIMARY KEY AUTOINCREMENT`; `session_id TEXT NOT NULL`; `created_at TEXT NOT NULL`; `user_text TEXT NOT NULL`; `reply TEXT NOT NULL`; `natural_expression TEXT`; `encouragement TEXT`; `pronunciation_score INTEGER`; `recognition_confidence INTEGER` |
| `corrections` | `id INTEGER PRIMARY KEY AUTOINCREMENT`; `turn_id INTEGER NOT NULL`; `original TEXT`; `corrected TEXT`; `explanation TEXT`; `error_type TEXT`; `review_count INTEGER DEFAULT 0`; `correct_streak INTEGER DEFAULT 0`; `next_review_at TEXT`; `last_reviewed_at TEXT` |

`turns.pronunciation_score` is present in the table creation SQL, but the
current `save_turn()` writes its score argument to `recognition_confidence`.
Summary queries alias `recognition_confidence` as `pronunciation_score` for
response-building compatibility. This naming does not mean the score measures
pronunciation accuracy.

## 32. Database Relationships

```text
sessions.id  1 ─────────── * turns.session_id
turns.id     1 ─────────── * corrections.turn_id
```

The foreign keys are declared with `REFERENCES`; `get_connection()` enables
SQLite foreign-key enforcement. The source does not declare cascading deletes.
Indexes are `idx_turns_session` on `turns(session_id)` and
`idx_corrections_turn` on `corrections(turn_id)`.

## 33. Data Flow

1. Browser gathers typed text or audio.
2. For audio, `/api/transcribe` returns transcript and optional word
   probabilities.
3. Browser submits the transcript/text plus session ID to `/api/chat`.
4. Backend reads previous turns, constructs LLM messages, and calls the
   selected LLM.
5. Backend parses reply/corrections, computes IPA and confidence metadata,
   and inserts the turn and correction rows.
6. Browser renders the returned conversation response.
7. Optional review, dashboard, and summary screens query SQLite through their
   corresponding API endpoints.
8. Playback sends text to `/api/tts`; the browser uses SpeechSynthesis if
   server-side playback fails.

## 34. Text Conversation Flow

The send button or Enter key calls `sendText()`. It trims the input, prevents
empty or overlapping requests, clears the text field, and invokes
`submitTurn()`. That function posts JSON to `/api/chat`, displays an error if
the response is not successful, otherwise calls `renderTurn()`. The user's
typed turn does not include word-level ASR probabilities, so its
`pronunciation_score.overall_score` is normally unavailable.

## 35. Voice Conversation Flow

The user records a clip in the browser. `MediaRecorder` creates the blob;
`transcribeAndSend()` uploads it to `/api/transcribe`. After a successful
transcription, the page uses the returned text and `words` to call
`submitTurn()`/`/api/chat`. The rendered turn includes a button for replaying
the original recorded audio, plus correction and tutor response content.

## 36. AI Processing Flow

For conversation, `get_llm_response` selects the provider. Ollama is the
default provider in code, OpenAI and Anthropic are alternative branches.
`SYSTEM_PROMPT` guides corrections and reply; `parse_llm_json` extracts
structured output. Summary feedback uses a separate prompt and call. The
dashboard statistics and review answer judgement are deterministic Python/
SQLite operations and do not require an LLM.

## 37. TTS Flow

```text
UI play action
  → speak(text)
  → POST /api/tts
  → edge-tts or OpenAI TTS
  → audio/mpeg response
  → browser Audio playback
  → Web Speech API fallback if request/playback fails
```

Listening mode additionally hides the reply text until tapped and attempts
automatic playback of the assistant reply.

## 38. STT Flow

```text
Mic click → getUserMedia → MediaRecorder → audio Blob
  → multipart POST /api/transcribe
  → local faster-whisper or OpenAI transcription
  → transcript (+ local per-word metadata when supplied)
  → POST /api/chat
```

There is no client-side `SpeechRecognition`/`webkitSpeechRecognition` usage
in the current frontend; microphone audio is sent to the server-side
transcription route.

## 39. Database Flow

`chat()` calls `db.get_history()` before the LLM call and
`db.save_turn()` after successful response parsing. `save_turn()` creates a
session if necessary, inserts a turn, tags and inserts each dictionary-shaped
correction, then commits through the connection context manager. Stats and
review routes call their matching query/update helpers. Session summary loads
session turns and corrections, builds statistics, then optionally requests
LLM feedback.

## 40. Configuration

`config.py` reads a local `.env` if it exists. Its simple loader skips blank
lines, comments, and lines without `=`, strips surrounding quotes, and uses
`os.environ.setdefault`; already-set process environment values take
precedence. Settings not obtained from environment variables include
`HOST="0.0.0.0"`, `PORT=8443`, certificate filenames, API version/token
constants, and `MAX_CONVERSATION_HISTORY=20`.

Defaults in `config.py` can differ from values in `.env.example`. For example,
the Python fallback model is `gemma2:latest`, while the example file sets
`ornith:9b`.

## 41. Environment Variables

| Variable(s) | Purpose |
|---|---|
| `LLM_PROVIDER` | `ollama`, `openai`, or `anthropic`; code default `ollama`. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Ollama service address and model tag. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI chat provider credentials/model. |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Anthropic chat provider credentials/model. |
| `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE` | OpenAI speech synthesis settings. |
| `OPENAI_WHISPER_MODEL`, `OPENAI_TRANSCRIPTION_LANGUAGE` | OpenAI transcription settings. |
| `TTS_PROVIDER` | `edge`, `openai`, or `browser`; default `edge`. |
| `EDGE_TTS_VOICE`, `EDGE_TTS_RATE` | Edge TTS voice and rate. |
| `STT_PROVIDER` | `faster_whisper`, `openai`, or `disabled`; default `faster_whisper`. |
| `FASTER_WHISPER_MODEL`, `FASTER_WHISPER_LANGUAGE` | Local transcription model/language. |
| `FASTER_WHISPER_DEVICE`, `FASTER_WHISPER_COMPUTE_TYPE` | Runtime device and numeric compute mode. |
| `FASTER_WHISPER_CPU_THREADS`, `FASTER_WHISPER_NUM_WORKERS`, `FASTER_WHISPER_BEAM_SIZE` | Local inference performance controls. |
| `FASTER_WHISPER_VAD_FILTER` | Boolean-like VAD setting (`1`, `true`, `yes`, `on`). |
| `FASTER_WHISPER_DOWNLOAD_ROOT` | Optional model download directory. |
| `FASTER_WHISPER_LOCAL_FILES_ONLY` | Boolean-like local-only model loading setting. |

The `.env.example` contains example provider values and a placeholder API key,
not a real credential. No secret values are included in this document.

## 42. Dependencies

The complete `requirements.txt` manifest lists:

- `fastapi`
- `uvicorn[standard]`
- `httpx`
- `nltk`
- `eng-to-ipa`
- `cryptography`
- `python-multipart`
- `faster-whisper`
- `edge-tts`

Python standard-library dependencies include `sqlite3`, `asyncio`, `json`,
`re`, `subprocess`, `tempfile`, `pathlib`, `datetime`, and `threading`.
OpenAI and Anthropic are accessed using `httpx`; no dedicated SDK for either
provider appears in `requirements.txt`.

## 43. Local vs Online Components

| Component | Runtime location / network behavior |
|---|---|
| FastAPI app and SQLite | Run locally. |
| Ollama | Local by default at `http://localhost:11434`; can be pointed elsewhere. |
| faster-whisper | Runs locally after package/model availability; first model download may require network unless already present or local-only mode is selected. |
| OpenAI LLM/STT/TTS | Cloud API calls; require network and valid credentials. |
| Anthropic LLM | Cloud API call; requires network and valid credentials. |
| edge-tts | Server package streams audio from a network-backed service; requires network. |
| Browser SpeechSynthesis | Browser/OS-provided voices; no project voice model is bundled. |
| IPA resources | `eng_to_ipa` and NLTK dictionary; startup code calls `nltk.download('cmudict')`, which may need network if the resource is not already available. |

README calls the local Ollama mode private inference; implementation sends
conversation messages to the configured Ollama base URL. Privacy therefore
depends on the actual service address and deployment configuration.

## 44. HTTPS / SSL

`config.py` fixes the server port at 8443 and certificate names to `cert.pem`
and `key.pem`. The `__main__` block of `server.py` calls
`generate_self_signed_cert()`, prints discovered access URLs, and passes
certificate paths to `uvicorn.run` when both files exist.

The helper gathers host, local IPv4, and optional Tailscale DNS names and adds
them to a self-signed RSA 2048 certificate's Subject Alternative Name. It
checks whether an existing certificate covers current names/IPs before
reusing it. Self-signed certificates produce browser trust warnings and are
development certificates, not certificates from a trusted authority.

## 45. Security

Verified security-relevant facts:

- `.gitignore` excludes `.env`, generated certificates/keys, SQLite data, and
  common caches/virtual environments.
- `.env.example` is a placeholder configuration file.
- Provider credentials are read from environment variables or `.env`.
- SQL queries for user/session values use SQLite parameter placeholders in
  query operations.
- The app enables permissive CORS and binds to `0.0.0.0`; it does not contain
  an authentication or authorization layer in the inspected routes.
- Self-signed HTTPS encrypts a connection but does not provide publicly trusted
  identity.
- No credentials or local `.env` values are reproduced in this document.

The README advises configuring production-grade HTTPS, authentication, CORS,
and secret management before public deployment. Public deployment hardening
is not implemented by the current source.

## 46. Error Handling

Examples verified in source:

- Empty chat/TTS text: HTTP 400.
- Upload empty: HTTP 400; upload over 25 MiB: HTTP 413.
- Unsupported provider: HTTP 500 with provider name.
- Missing provider keys/packages or disabled server features: generally HTTP
  503.
- Provider HTTP/API errors: mapped to HTTP 502 in speech paths; Ollama has
  connection and fallback error handling.
- Empty recognized speech: HTTP 422.
- Unknown correction: HTTP 404.
- Summary for a session with no turns: HTTP 404; the frontend displays a toast.
- LLM summary feedback failure: logged to stdout, feedback becomes `null`,
  and summary statistics still return with HTTP 200.
- Frontend fetch failures are displayed in the related status area/overlay or
  conversation error card.

Some health/model lookup code uses fallback readiness/list responses. The
health endpoint reports configured readiness indicators and should not be
interpreted as a complete provider integration test.

## 47. Testing

### Tests

**Purpose:** Check ASR confidence calculations, database summary queries,
summary JSON parsing, and summary API response paths with a mocked LLM.

**Files:** `test_speech_confidence.py`, `test_summary.py`.

**Function(s):** `test_asr_confidence_is_plain_average_without_pronunciation_penalty`,
`test_missing_word_probabilities_is_reported_as_unavailable`,
`test_db_get_session_summary_data`, `test_parse_summary_llm_json`, and
`test_api_summary`.

**Input:** Small English sample values, a temporary SQLite database, and
mocked LLM result/failure responses.

**Processing:** The confidence test checks arithmetic and unavailable input;
summary tests exercise database helpers, parser fallback/normalization, API
success, LLM failure, unknown session, and malformed JSON.

**Output:** Assertions; `test_summary.py` prints a count when run directly.

**Dependencies:** The app dependencies and `fastapi.testclient.TestClient`;
pytest is needed to collect the pytest-style tests.

**How it connects with other modules:** Imports `server.py`, `db.py`, and the
confidence function; the summary script swaps `db.DB_PATH` for a temporary
file and replaces the LLM call with async mocks.

**Simple explanation:** Tests use fake conversations so they can check core
behavior without a live LLM.

**Viva explanation:** The summary API test verifies functional behavior using
FastAPI's TestClient and dependency substitution rather than requiring
networked model services.

Commands documented by the repository:

```bash
python test_summary.py
pytest
```

The README specifically documents the direct summary smoke test. No automated
test suite for live Ollama, live Edge TTS, or live faster-whisper microphone
capture is present in the tracked test files.

## 48. Current Working Features

Features whose corresponding source paths were verified:

- Serving the single-page English Bee application.
- Text conversation through a configured LLM provider.
- Grammar correction and optional natural-expression generation as prompted
  LLM output.
- Persistent session/turn/correction storage.
- Microphone audio recording and server-side transcription.
- ASR word-probability aggregation when those values are present.
- IPA data generation and display for user text.
- Error-type classification and statistics.
- Correction review with exact/near text comparison and review intervals.
- Summary statistics and LLM-generated summary feedback.
- Edge/OpenAI server TTS branches and browser speech fallback.
- Health/model listing routes and local certificate helper.

Whether each external integration works on a particular machine depends on
configuration, installed packages, hardware, model availability, network, and
credentials.

## 49. Features NOT Implemented

The following should be described as **Not implemented in the current
version** based on the inspected files:

- User sign-up, login, password storage, roles, or user-specific data access.
- Production-grade authentication, authorization, or deployment controls.
- Session deletion, editing, or selecting an earlier session in the UI.
- Cloud synchronization or multi-device account synchronization.
- Audio waveform visualization or pronunciation alignment against a reference
  recording.
- Automated phoneme/accent/stress/rhythm/intelligibility scoring.
- A client-side Web Speech `SpeechRecognition` transcription flow.
- A dedicated frontend framework/build pipeline.
- Automated end-to-end tests against real remote/local provider services.

An API route may expose read-only session/correction data even when a matching
session-management UI action is absent. The presence of an API should not be
mistaken for full CRUD or account management.

## 50. Limitations

- LLM correction quality depends on the selected model and prompt compliance.
- JSON parsing is tolerant but is not a full schema-validation layer for every
  returned field.
- `error_tagger.py` uses keywords and a finite set of diff heuristics; unknown
  patterns may be categorized as `other` or misclassified.
- ASR confidence is not pronunciation-quality measurement.
- IPA depends on available dictionary/library coverage; unknown words may have
  no IPA value.
- Local transcription speed and accuracy depend on the model and device.
- Edge TTS and cloud provider modes require network access.
- `sessionId` is regenerated on page load and is not restored from persistent
  browser storage.
- Local self-signed TLS produces trust prompts and is not production PKI.
- The checked-in README's default model example differs from `.env.example`
  and the Python fallback.
- `lang="ja"` remains on the HTML document despite English visible copy.

## 51. Future Scope

Possible future work (suggestions only; not claims of existing behavior):

- Add a secure user/account model before multi-user deployment.
- Add session selection, deletion, and export with explicit ownership checks.
- Add deterministic request/response schemas and broader automated tests.
- Add a provider connectivity test separate from configuration readiness.
- Add optional audio alignment and a validated pronunciation assessment
  pipeline, clearly separate from ASR confidence.
- Improve classifier coverage with evaluated examples and test cases.
- Add trusted certificate/deployment documentation and restrictive CORS
  configuration for non-local hosting.
- Resolve model default discrepancies between README, `.env.example`, and
  `config.py`.
- Correct document language metadata to match the user-facing language if the
  maintainers choose to do so.

## 52. College Project Report Content

### Abstract

AI English Conversation Tutor is a browser-based learning application built
with FastAPI, Python, JavaScript, and SQLite. It supports text chat and
microphone recording, uses configurable LLM and speech services to provide
conversation feedback, stores corrections, and offers review and summary
views. The system returns ASR recognition confidence where the transcription
provider supplies word probabilities. This confidence is not a pronunciation
accuracy score.

### Aim

To create a local-first English practice tool that combines conversational
practice, correction history, review, and speech playback in one application.

### Method

The frontend submits text or audio to FastAPI. Speech audio is transcribed
through the selected STT provider. The `/api/chat` handler builds a system
prompt and conversation history, calls the selected LLM, parses the response,
generates IPA information, calculates available ASR confidence, and stores
the exchange in SQLite. Additional endpoints provide review, statistics,
summary, and TTS.

### Result

The source implements text and microphone workflows, provider selection,
SQLite-backed review/dashboard/summary routes, and fallback speech playback.
The degree of operation depends on having the required providers, models,
permissions, network, and credentials available.

### Conclusion

The project demonstrates integration of a browser UI, REST APIs, local
persistence, LLM prompts, speech recognition, speech synthesis, and automated
tests. It is suitable as a learning prototype; the current source does not
provide production user authentication or a validated pronunciation-quality
assessment.

## 53. 3–5 Minute College Presentation Script

> Good morning. My project is the AI English Conversation Tutor, whose browser
> interface is called English Bee. It is designed to help an English learner
> practice through text or recorded speech and review previous corrections.
>
> The frontend is a single HTML file, `static/index.html`, containing the
> page's HTML, CSS, and JavaScript. The backend is `server.py`, which uses
> FastAPI to expose REST endpoints. `config.py` selects the LLM, transcription,
> and speech providers. `db.py` saves sessions, conversation turns, and
> corrections in SQLite.
>
> In a text conversation, the browser sends the text and a session ID to
> `POST /api/chat`. The backend loads recent turns, combines them with a system
> prompt, and calls the configured LLM. Ollama is the local provider path;
> OpenAI and Anthropic are optional code paths. The model is asked to return a
> short reply, corrections, and an optional natural expression. The backend
> parses the response, generates IPA data, calculates available
> speech-recognition confidence, saves the turn, and returns JSON to the page.
>
> For speaking practice, the browser records audio with `MediaRecorder` and
> uploads it to `POST /api/transcribe`. The default STT provider is
> faster-whisper. The returned transcript is then sent through the same chat
> endpoint. When word probabilities are present, the app displays their
> average as ASR confidence. This is confidence in the transcription, not a
> direct assessment of pronunciation.
>
> The database has three main tables: `sessions`, `turns`, and `corrections`.
> Corrections are tagged by `error_tagger.py`. Review mode compares a learner's
> answer with the correction using normalized text and a similarity threshold,
> then schedules another review using simple spaced intervals.
>
> Speech playback first calls the server TTS endpoint. Edge TTS is the
> example configuration, and browser SpeechSynthesis is the fallback. This
> means local LLM and transcription do not necessarily mean every feature is
> offline.
>
> The project also provides a weakness dashboard and a session summary.
> Summary statistics are calculated in Python, while short qualitative
> feedback is requested from the LLM. The test files check confidence
> calculations, database summaries, parsing, and API behavior using a
> temporary database and mocked model calls.
>
> In conclusion, this project demonstrates how a static browser interface can
> work with FastAPI, configurable AI and speech services, and SQLite. It is a
> local learning prototype. Authentication, multi-user access, and validated
> pronunciation scoring are not implemented. Thank you.

## 54. 40+ Viva Questions and Answers

1. **What is the project?** — A browser-based English conversation practice
   tutor with feedback, review, persistence, and speech features.
2. **What is its UI name?** — English Bee, shown in `static/index.html`.
3. **What is the backend framework?** — FastAPI.
4. **What starts the web server?** — Uvicorn, invoked in `server.py`.
5. **What is the frontend stack?** — Static HTML, CSS, and vanilla JavaScript.
6. **Where is the frontend?** — `static/index.html`.
7. **Where is configuration loaded?** — `config.py`, including optional `.env`.
8. **Where is database logic?** — `db.py`.
9. **Which database is used?** — SQLite via the standard-library `sqlite3`.
10. **What are the main tables?** — `sessions`, `turns`, and `corrections`.
11. **What is one turn?** — A user's message and the assistant's response.
12. **How are turns linked to sessions?** — `turns.session_id` references
    `sessions.id`.
13. **How are corrections linked?** — `corrections.turn_id` references
    `turns.id`.
14. **What is `/api/chat` for?** — LLM conversation and feedback processing.
15. **What method does `/api/chat` use?** — POST with JSON.
16. **What does `ChatRequest` contain?** — `text`, `session_id`, `confidence`,
    and `words` fields.
17. **Where is the main tutor prompt?** — `config.SYSTEM_PROMPT`.
18. **Does the prompt guarantee correct grammar feedback?** — No; it instructs
    the LLM but output quality depends on the model.
19. **How does Ollama get the conversation?** — `call_ollama` sends messages
    to `/api/chat`, with a fallback to `/api/generate`.
20. **What is the local Ollama URL default?** — `http://localhost:11434`.
21. **What is `ornith:9b`?** — The model tag in `.env.example`; its model
    internals are not documented in this repository.
22. **Does the Python config default match that example?** — No; fallback is
    `gemma2:latest`, while `.env.example` sets `ornith:9b`.
23. **What does `MAX_CONVERSATION_HISTORY=20` mean?** — Up to 20 messages,
    normally 10 earlier user/assistant turns.
24. **Does the browser remember its session ID after reload?** — No; it
    generates a timestamp-based ID in JavaScript.
25. **Does Reset erase SQLite data?** — No; it clears the page and creates a
    new client-side session ID.
26. **How does STT work?** — Browser audio is uploaded to `/api/transcribe`.
27. **Which STT provider is default in config?** — `faster_whisper`.
28. **Which model is the example STT model?** — `base.en`.
29. **Does the browser use the Web Speech Recognition API?** — No; it records
    audio and sends it to the server.
30. **What does word probability mean here?** — The ASR model's confidence in
    recognized words, not measured pronunciation accuracy.
31. **How is IPA generated?** — `eng_to_ipa` is preferred, then the NLTK
    CMU dictionary/ARPAbet conversion is used when available.
32. **What does `error_tagger.py` do?** — Assigns correction categories from
    explanation keywords and simple text-diff heuristics.
33. **Is error tagging an LLM call?** — No; it is rule-based.
34. **How does review judgement work?** — Normalize case/spacing/trailing
    punctuation; compare exact equality, then `SequenceMatcher` similarity.
35. **What makes an answer “close”?** — A non-exact similarity ratio at least
    `0.85`.
36. **What are the SRS intervals?** — 1, 3, 7, 14, and 30 days after
    consecutive correct answers; incorrect answers retry in one day.
37. **What does the dashboard show?** — Turn/correction totals, average ASR
    confidence, error categories/examples, and recent confidence trend.
38. **How is session summary feedback built?** — Rule-based statistics plus
    one LLM feedback call; on feedback failure, statistics still return.
39. **What is `/api/pronunciation`?** — A POST route returning IPA data for
    supplied text.
40. **What is the default TTS provider?** — `edge` in `config.py` and
    `.env.example`.
41. **Is Edge TTS offline?** — No; it uses a network-backed service.
42. **What happens if server TTS fails?** — The frontend attempts browser
    SpeechSynthesis.
43. **What does `GET /api/health` prove?** — It reports provider names and
    readiness flags; Ollama readiness is not a live connectivity test.
44. **How does the app serve its frontend?** — `GET /` returns the HTML file;
    `/static` serves assets.
45. **Why use SQLite?** — It provides local persistence without a separate
    database service.
46. **How are database writes committed?** — The connection context manager
    commits on success and rolls back on exceptions.
47. **What are the main security limitations?** — No auth layer is present,
    CORS is permissive, and the server binds to all interfaces by default.
48. **Is the generated certificate publicly trusted?** — No; it is
    self-signed for local development.
49. **Which route exposes due reviews?** — `GET /api/review/due`.
50. **Which route records an answer?** — `POST /api/review/answer`.
51. **What tests are present?** — ASR confidence tests and summary/database/API
    tests with a temporary DB and mocked LLM.
52. **Does the source provide user accounts?** — No, not in the current
    version.
53. **Does it truly score pronunciation?** — No; ASR confidence is not
    pronunciation-quality scoring.
54. **Can it run entirely offline?** — Some local paths can; Edge TTS, first
    model/resource downloads, and cloud providers may require network.
55. **Why parse model JSON?** — To transform LLM output into predictable
    response fields and tolerate code fences or surrounding text.

## 55. Easy Hinglish Explanation

Yeh project English practice ke liye ek browser app hai. User sentence type
kar sakta hai ya microphone se audio record kar sakta hai. Text ke liye page
FastAPI ke `/api/chat` endpoint ko request bhejta hai. Backend previous turns
SQLite se leta hai, system prompt ke saath selected LLM ko call karta hai, aur
reply/corrections wapas browser ko deta hai.

Voice use karne par browser `MediaRecorder` se audio banata hai aur
`/api/transcribe` ko bhejta hai. Default local STT `faster-whisper` hai.
Transcript phir chat endpoint ko jata hai. Agar ASR word probabilities milti
hain to unka average confidence ke roop mein dikhaya jata hai; yeh pronunciation
accuracy ka score nahi hai.

`db.py` SQLite mein sessions, turns aur corrections rakhta hai.
`error_tagger.py` rule-based correction category banata hai. Review mode
answer ko normalized text se compare karta hai aur correct answer ke baad
review interval badhata hai. Speech ke liye default example Edge TTS hai; yeh
network use karta hai, aur failure par browser SpeechSynthesis try hota hai.

Simple terms mein: frontend user input leta hai, backend AI/speech/database
ka kaam karta hai, aur SQLite learning history save karta hai. App local
learning prototype hai; login aur real pronunciation scoring implemented
nahi hain.

## 56. Professional English Explanation

The application is a local-first, browser-based language-practice prototype.
Its static JavaScript client communicates with a FastAPI service through
same-origin HTTP endpoints. The service coordinates configurable LLM and
speech providers, stores exchanges and correction metadata in SQLite, and
exposes review, dashboard, and session-summary operations. Its speech
confidence metric represents ASR transcription confidence rather than
pronunciation quality. External services and hardware-dependent components
remain subject to their own availability, credentials, and network
requirements.

## 57. Technical Glossary

| Term | Meaning in this project |
|---|---|
| API | HTTP interface used by the browser and backend integrations. |
| ASR | Automatic Speech Recognition; converts recorded audio into text. |
| CORS | Browser cross-origin access policy configured by FastAPI middleware. |
| CMU Dictionary | Pronunciation dictionary accessed through NLTK `cmudict`. |
| FastAPI | Python framework providing typed HTTP routes and request parsing. |
| IPA | International Phonetic Alphabet; shown as a text pronunciation guide. |
| LLM | Large Language Model used for conversation and generated feedback. |
| Ollama | Local model runtime called over its HTTP API. |
| SRS | Spaced Repetition System; here a simple set of day-based review intervals. |
| SQLite | Embedded relational database stored in a local file. |
| STT | Speech-to-Text; transcription of audio into text. |
| TTS | Text-to-Speech; synthesis of audio from text. |
| `MediaRecorder` | Browser API used to record microphone audio. |
| `SpeechSynthesis` | Browser API used as a text-to-speech fallback. |
| `SequenceMatcher` | Python `difflib` utility used to calculate review answer similarity. |
| SAN | Subject Alternative Name extension in an X.509 certificate. |
| JSON | Data format used for chat, review, stats, and summary requests/responses. |

## 58. Complete End-to-End User Journey

1. The user opens the app over a local address, typically
   `https://localhost:8443`.
2. FastAPI serves `static/index.html`; JavaScript checks `/api/health`.
3. The user chooses text or microphone input.
4. For text, the browser sends the message to `/api/chat`. For audio, it
   records, uploads to `/api/transcribe`, and sends the returned transcript to
   `/api/chat`.
5. The backend retrieves session history, invokes the configured LLM, parses
   output, obtains IPA and confidence information, and saves the turn.
6. The browser shows the user message, correction cards, optional natural
   expression, and tutor response. Playback buttons call `/api/tts`, with
   browser speech as fallback.
7. The user may open the Stats view, which requests `/api/stats`, or Review,
   which requests `/api/review/due` and submits answers to
   `/api/review/answer`.
8. Finish requests `/api/summary/{session_id}`. The backend builds local
   statistics and attempts a separate LLM feedback request.
9. Closing the summary invokes the new-session/reset flow. Existing database
   rows remain stored.

## 59. “What Happens When User Types Hi?”

1. `sendText()` trims `"Hi"` and calls `submitTurn("Hi", 0, null)`.
2. `submitTurn()` posts JSON similar to
   `{"text":"Hi","session_id":"...","confidence":0,"words":[]}`.
3. `/api/chat` validates non-empty text and loads any previous messages for
   that session.
4. The system prompt, history, and `"Hi"` are sent to the selected LLM.
5. The LLM is asked for a short English reply, corrections, and a
   `natural_expression` value in JSON. The exact output is model-dependent;
   it should not be hard-coded in documentation as a guaranteed response.
6. `parse_llm_json()` extracts the structured response or falls back to text.
7. The server generates IPA data, determines ASR confidence (normally
   unavailable for typed text), saves the turn, and returns JSON.
8. The page renders the user text and AI response. Any model-generated
   correction or natural expression is displayed if present.

## 60. “What Happens When User Speaks?”

1. `toggleRecording()` calls `startRecording()` if not already recording.
2. The browser requests microphone permission and starts `MediaRecorder`.
3. A later mic-button press calls `stopRecording()`. The recorded chunks are
   assembled into a blob and uploaded as multipart `audio`.
4. `/api/transcribe` selects local `faster-whisper`, OpenAI transcription, or
   returns an error if disabled/unavailable.
5. The transcript and any local word-probability records are returned.
6. The page displays the transcript preview and submits it to `/api/chat`,
   passing the `words` array.
7. The chat response is stored and rendered; the user may replay the recorded
   clip or request synthesized speech.

## 61. Final Technical Summary

The verified system is a single-page English practice UI backed by FastAPI.
`server.py` orchestrates text chat, optional remote/local LLMs, server-side
speech recognition, TTS, IPA conversion, review, stats, and summaries.
`config.py` reads provider configuration; `db.py` stores SQLite session,
turn, and correction records; `error_tagger.py` and `review_logic.py` provide
rule-based supporting behavior.

The checked-in example uses Ollama with model tag `ornith:9b`, local
`faster-whisper` with `base.en`, and Edge TTS. Code defaults and README example
do not all match those sample values. Actual operation depends on the local
environment. The repository implements ASR confidence display, not
pronunciation-quality scoring, and does not implement authentication or
multi-user management.

## 62. Verified From Source Code Checklist

The following items were checked against the tracked source files, route
definitions, configuration, and tests before writing this document:

- [x] Frontend analyzed
- [x] Backend analyzed
- [x] API endpoints analyzed
- [x] Database analyzed
- [x] Ollama analyzed
- [x] LLM configuration analyzed
- [x] STT analyzed
- [x] TTS analyzed
- [x] IPA/pronunciation analyzed
- [x] Configuration analyzed
- [x] Dependencies analyzed
- [x] Error handling analyzed
- [x] Security analyzed
- [x] Project structure analyzed
- [x] Implemented features verified
- [x] Missing features verified
- [x] Complete user flow verified

# SOURCE CODE VERIFICATION

- [x] Frontend analyzed
- [x] Backend analyzed
- [x] API endpoints analyzed
- [x] Database analyzed
- [x] Ollama analyzed
- [x] LLM configuration analyzed
- [x] STT analyzed
- [x] TTS analyzed
- [x] IPA/pronunciation analyzed
- [x] Configuration analyzed
- [x] Dependencies analyzed
- [x] Error handling analyzed
- [x] Security analyzed
- [x] Project structure analyzed
- [x] Implemented features verified
- [x] Missing features verified
- [x] Complete user flow verified
