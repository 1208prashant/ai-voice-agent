# VoiceOps AI Assistant

An open-source, voice-first AI mentor for DevOps, Linux, Docker, and cloud workflows. Speak or type your question in **English, Hindi, Marathi, Gujarati**, or other Indian languages — the assistant listens, reasons with **Google Gemini**, searches the web when needed, remembers context, and responds with natural speech via **Sarvam AI**.

---

## Objective

Technical work often happens **hands-on** — at a terminal, on a server, or while debugging. Reading long docs or typing detailed questions is slow in those moments.

**VoiceOps AI Assistant** solves that by providing a **spoken technical mentor** that:

1. Accepts **voice or text** input
2. Understands **multilingual** queries (auto-detected by Sarvam STT)
3. Gives **step-by-step guidance** powered by Gemini
4. Fetches **live information** from the web when documentation or versions change
5. **Remembers** the conversation within a session
6. Replies with **human-like speech** in the user's language

The goal is not to replace documentation — it is to act like a **patient senior engineer** sitting beside you, explaining the *why* behind commands while you work.

---

## Benefits

| Benefit | Description |
|--------|-------------|
| **Hands-free learning** | Ask questions by voice while your hands stay on the keyboard or server |
| **Multilingual support** | Hindi, Marathi, Gujarati, English, and more via Sarvam auto-detect |
| **Context-aware replies** | SQLite session memory keeps multi-turn conversations coherent |
| **Up-to-date answers** | Optional Tavily web search for versions, release notes, and current docs |
| **Natural voice output** | Sarvam Bulbul TTS with configurable pace and warmth |
| **Human persona** | "Arjun" dev-mentor persona — warm, encouraging, not a robotic FAQ bot |
| **Self-hostable** | FastAPI backend you control; no vendor lock-in for the app layer |
| **API + Web UI + CLI** | Use in browser, terminal, or integrate via REST |
| **Cost-effective stack** | Gemini free tier + Sarvam credits + Tavily free tier for prototyping |

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Web UI /   │     │   FastAPI        │     │  Google Gemini  │
│  CLI Client │────▶│   Agent Service  │────▶│  (reasoning)    │
└─────────────┘     │                  │     └─────────────────┘
       │            │  ┌────────────┐  │              │
       │            │  │ Session    │  │     ┌────────▼────────┐
       │            │  │ Memory     │  │     │  Tavily Search    │
       │            │  │ (SQLite)   │  │     │  (optional)     │
       │            │  └────────────┘  │     └─────────────────┘
       │            └────────┬─────────┘
       │                     │
       ▼                     ▼
┌──────────────┐     ┌──────────────┐
│ Sarvam STT   │     │ Sarvam TTS   │
│ (Saarika)    │     │ (Bulbul v3)  │
└──────────────┘     └──────────────┘
```

**Request flow (voice):**

1. User holds **Talk** button → browser records audio
2. **Sarvam STT** transcribes audio and detects language (`language_code=unknown`)
3. **Agent** loads session history, resolves language, calls **Gemini**
4. If needed, **Tavily** searches the web; Gemini synthesizes an answer
5. Response saved to **SQLite**; **Sarvam TTS** speaks in the user's language
6. Web UI plays audio and shows transcript + reply

---

## Features

- **Voice input** — hold-to-talk web UI + CLI microphone mode
- **Speech-to-text** — Sarvam Saarika v2.5 with automatic language detection
- **Gemini integration** — mentoring, tool calling, model fallback on rate limits
- **Web search** — Tavily API with automatic `search_web` tool use
- **Text-to-speech** — Sarvam Bulbul v3, multilingual (`SARVAM_LANGUAGE_CODE=auto`)
- **Conversation memory** — SQLite sessions with TTL and turn limits
- **Personas** — `dev-mentor` (Arjun) and `support-coach` (Meera)
- **REST API** — full programmatic access with OpenAPI docs at `/docs`

### Supported languages (via Sarvam)

English, Hindi, Marathi, Gujarati, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia (`*-IN` BCP-47 codes).

---

## Quick Start

### Prerequisites

- Python **3.9+**
- Microphone (for voice mode)
- API keys (see [Configuration](#configuration))

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-voice-agent.git
cd ai-voice-agent
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your keys (see table below).

> **Security:** Never commit `.env` to Git. It is listed in `.gitignore`. Use `.env.example` as the template only.

### 4. Start the server

```bash
python main.py
```

Open:

- **Web UI:** [http://127.0.0.1:8080](http://127.0.0.1:8080)
- **API docs:** [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

### 5. CLI client

**Text mode:**

```bash
python scripts/voice_client.py --mode text
```

**Voice mode:**

```bash
python scripts/voice_client.py --mode voice --duration 5
```

**Health check:**

```bash
python scripts/voice_client.py --health
```

---

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key — [aistudio.google.com](https://aistudio.google.com/apikey) |
| `SARVAM_API_KEY` | For voice | Sarvam STT + TTS — [dashboard.sarvam.ai](https://dashboard.sarvam.ai/) |
| `TAVILY_API_KEY` | Optional | Web search — [tavily.com](https://tavily.com) (1,000 free credits/month) |
| `GEMINI_MODEL` | No | Default: `gemini-2.5-flash-lite` |
| `SARVAM_STT_LANGUAGE_CODE` | No | Use `unknown` for auto-detect (recommended) |
| `SARVAM_LANGUAGE_CODE` | No | Use `auto` to match user language (recommended) |
| `ASSISTANT_PERSONA` | No | `dev-mentor` (Arjun) or `support-coach` (Meera) |
| `PORT` | No | Default: `8080` |

See `.env.example` for the full list.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Service status |
| `GET` | `/api/persona` | Assistant name, greeting, supported languages |
| `POST` | `/api/chat/text` | Text chat with session memory |
| `POST` | `/api/chat/voice` | Audio in → transcript + text response (JSON) |
| `POST` | `/api/chat/voice/full` | Audio in → spoken audio response |
| `POST` | `/api/stt` | Speech-to-text only |
| `POST` | `/api/tts` | Text-to-speech only |
| `GET` | `/api/sessions/{id}/history` | Conversation history |
| `DELETE` | `/api/sessions/{id}` | Clear session |

### Example: text chat

```bash
curl -X POST http://127.0.0.1:8080/api/chat/text \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I check disk usage on Linux?"}'
```

### Example: TTS with language

```bash
curl -X POST http://127.0.0.1:8080/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "नमस्ते, मैं आपकी मदद कर सकता हूँ।", "language_code": "hi-IN"}' \
  --output reply.wav
```

---

## Project Structure

```
ai-voice-agent/
├── main.py                    # FastAPI entrypoint
├── requirements.txt
├── .env.example               # Template (safe to commit)
├── .gitignore                 # Excludes .env, .venv, data/*.db
├── LICENSE
├── static/
│   └── index.html             # Web UI (hold-to-talk)
├── scripts/
│   └── voice_client.py        # CLI text/voice client
└── src/
    ├── config.py              # Settings from environment
    ├── persona.py             # Arjun / Meera personas
    ├── api/
    │   ├── routes.py          # REST endpoints
    │   └── schemas.py         # Pydantic models
    ├── memory/
    │   └── session_store.py   # SQLite session persistence
    └── services/
        ├── agent_service.py   # Orchestration pipeline
        ├── gemini_service.py  # Gemini + tool calling + fallbacks
        ├── search_service.py  # Tavily web search
        ├── stt_service.py     # Sarvam speech-to-text
        ├── tts_service.py     # Sarvam text-to-speech
        ├── language_service.py# BCP-47 language helpers
        ├── speech_formatter.py# TTS text preparation
        └── voice_service.py   # Microphone utilities (CLI)
```

---

## Usage Examples

### Scenario 1: Learn a Linux command (English)

**You (voice):** "How do I find large files on my server?"

**Arjun:** Explains `du` and `find`, gives a safe command, asks if you want help running it.

### Scenario 2: Docker help in Hindi

**You (voice):** "Docker Ubuntu par kaise install karein?"

**Flow:** Sarvam detects `hi-IN` → Gemini replies in Hindi → Sarvam TTS speaks in Hindi.

### Scenario 3: Current software version (web search)

**You:** "What is the latest stable Node.js LTS version?"

**Flow:** Gemini calls `search_web` → Tavily fetches results → answer includes current version.

---

## Security & API Keys

This project follows these rules to **prevent secret leaks**:

| File | Commit to Git? | Notes |
|------|----------------|-------|
| `.env` | **Never** | Contains real API keys — gitignored |
| `.env.example` | Yes | Placeholder values only |
| `data/sessions.db` | No | Local conversation data — gitignored |
| `.venv/` | No | Virtual environment — gitignored |

**Before pushing to GitHub, verify:**

```bash
# Should print nothing (no .env tracked)
git status

# Confirm .env is ignored
git check-ignore -v .env

# Scan staged files for accidental secrets (optional)
grep -r "AIzaSy\|sk_\|tvly-" --include='*.py' --include='*.html' --include='*.md' .
# Only .env.example placeholders should appear in tracked files
```

If you ever commit a key by mistake, **rotate the key immediately** at the provider dashboard and use `git filter-repo` or GitHub secret scanning remediation.

---

## Creating a Safe Archive (without secrets)

To share or back up the project without API keys:

```bash
cd /path/to/ai-voice-agent

tar -czvf ../ai-voice-agent-archive.tar.gz \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='data/*.db' \
  --exclude='data/*.db-journal' \
  --exclude='.git' \
  --exclude='*.wav' \
  --exclude='*.mp3' \
  .
```

The archive is created at `../ai-voice-agent-archive.tar.gz` with **no `.env` file**.

---

## Push to GitHub (CLI steps)

### Step 1 — Initialize Git (first time only)

```bash
cd ai-voice-agent
git init
```

### Step 2 — Verify secrets are excluded

```bash
git check-ignore -v .env
# Expected: .gitignore:2:.env    .env

cat .gitignore | head -5
```

### Step 3 — Stage and commit

```bash
git add .
git status
# Confirm .env, .venv/, and data/*.db are NOT listed

git commit -m "$(cat <<'EOF'
Initial commit: VoiceOps AI Assistant

Voice-first DevOps mentor with Gemini, Sarvam STT/TTS, multilingual
support, web search, and SQLite session memory.
EOF
)"
```

### Step 4 — Create a GitHub repository

1. Go to [github.com/new](https://github.com/new)
2. Name it `ai-voice-agent` (or your preferred name)
3. **Do not** initialize with README (you already have one)
4. Copy the repository URL

### Step 5 — Push to GitHub

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-voice-agent.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### Step 6 — (Optional) Use SSH instead of HTTPS

```bash
git remote add origin git@github.com:YOUR_USERNAME/ai-voice-agent.git
git push -u origin main
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `429 Too Many Requests` (Gemini) | Wait 30–60s; app auto-retries and falls back to alternate models |
| `Empty audio recording` | Hold Talk button longer; allow microphone permission |
| `SARVAM_API_KEY is required` | Add key to `.env` and restart server |
| Port 8080 in use | Change `PORT=8081` in `.env` |
| Wrong TTS language | Reset session; ensure `SARVAM_STT_LANGUAGE_CODE=unknown` |

---

## Roadmap (future phases)

- Wake word detection
- SSH / terminal awareness
- Desktop automation (with explicit user approval)
- Custom persona upload
- Deployment guides (Docker, Railway, Render)

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

- [Google Gemini](https://ai.google.dev/) — reasoning and tool use
- [Sarvam AI](https://www.sarvam.ai/) — Indian-language STT and TTS
- [Tavily](https://tavily.com/) — developer-focused web search API
- [FastAPI](https://fastapi.tiangolo.com/) — API framework
