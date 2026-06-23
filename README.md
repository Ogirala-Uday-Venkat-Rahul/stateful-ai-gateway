# Stateful AI Chat Gateway

A production-grade AI chat backend built with FastAPI, featuring persistent conversation memory, cloud LLM inference, and an in-memory rate limiting layer. Includes a Streamlit frontend for live demonstration.

---

## Architecture

```
[ Streamlit UI (app.py) ]
        |
        | HTTP POST /chat
        v
[ FastAPI Backend (main.py) ]
        |              |
        |              v
        |     [ Sliding-Window Rate Limiter ]
        |              |
        v              v
[ PostgreSQL (Koyeb) ] [ Groq Cloud API ]
  - Stores all             - llama-3.1-8b-instant
  - chat history           - OpenAI-compatible
  - by session ID          - >200 tokens/sec
```

---

## Features

- **Stateful Conversations** — full chat history stored in PostgreSQL and injected into every LLM call, giving the model persistent memory across turns
- **Session Management** — each client gets a unique UUID session token; multiple users can chat independently without history collision
- **Sliding-Window Rate Limiter** — in-memory IP-based limiter capped at 5 requests/minute; returns HTTP 429 on violation to protect backend resources
- **Cloud Inference** — routes to Groq Cloud (`llama-3.1-8b-instant`) via OpenAI-compatible API; zero local GPU load
- **SQL Injection Defense** — all database queries use parameterized `%s` placeholders; no raw string interpolation
- **Streamlit Frontend** — live chat UI with session diagnostics sidebar and graceful 429 error handling

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn (async) |
| Frontend UI | Streamlit |
| LLM Inference | Groq Cloud — `llama-3.1-8b-instant` |
| Persistence | PostgreSQL via `psycopg2-binary` |
| HTTP Client | httpx (async-compatible) |
| Validation | Pydantic v2 |
| Config | python-dotenv |

---

## Project Structure

```
ai-chat-api/
├── main.py            # FastAPI backend — chat endpoint, rate limiter, Groq integration
├── app.py             # Streamlit frontend — chat UI, session management
├── database.py        # PostgreSQL data layer — init, save, and retrieve chat history
├── requirements.txt   # Python dependencies
├── .env               # API keys — never committed (see .gitignore)
└── .gitignore
```

---

## Local Setup

**1. Clone the repo**
```bash
git clone https://github.com/YOUR_USERNAME/ai-chat-api.git
cd ai-chat-api
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Add your Groq API key**

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```
Get a free key at [console.groq.com](https://console.groq.com)

**4. Initialize the database**
```bash
python database.py init
```

**5. Start the FastAPI backend**
```bash
uvicorn main:app --reload
```

**6. Start the Streamlit frontend** (new terminal)
```bash
streamlit run app.py
```

Frontend runs at `http://localhost:8501` — backend API docs at `http://localhost:8000/docs`

---

## API Reference

### `POST /chat`

Accepts a message and session ID, returns the AI reply.

**Request body:**
```json
{
  "session_id": "sess_a3f7c291",
  "message": "What did I say earlier?"
}
```

**Response:**
```json
{
  "reply": "You asked about the rate limiter earlier in our conversation."
}
```

**Error responses:**
| Code | Meaning |
|---|---|
| `422` | Missing or invalid request fields |
| `429` | Rate limit exceeded (5 req/min per IP) |
| `502` | Groq Cloud unreachable |

---

## Key Design Decisions

**Why Groq over local Ollama?**
Local GPU constraint (4GB VRAM) posed crash risk under sustained load. Groq Cloud offloads inference entirely, delivers >200 tokens/sec, and uses an OpenAI-compatible API so the integration pattern is industry-standard.

**Why PostgreSQL over SQLite?**
SQLite uses the local filesystem, which is ephemeral on cloud platforms — data wipes on every restart. PostgreSQL runs as a managed service (Koyeb free tier), survives restarts, and is the industry standard for production deployments. The data layer is fully abstracted behind `database.py`, so the swap required changing only one file.

**Why a sliding window over a fixed window rate limiter?**
Fixed windows can be gamed — a client can send 5 requests at 11:59 and 5 more at 12:00, hitting 10 in under a second. A sliding window evaluates the true last-60-seconds window on every request, closing that gap.
