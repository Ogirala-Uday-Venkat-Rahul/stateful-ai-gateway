# Stateful AI Chat Gateway

Live demo: https://stateful-ai-gateway.streamlit.app

A FastAPI chat backend that remembers the conversation. It saves every message to PostgreSQL, sends the history back to the model on each request so the assistant has context, and rate-limits clients that hit it too hard. A small Streamlit frontend is included so you can try it without calling the API by hand.

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
[ PostgreSQL (Neon) ]  [ Groq Cloud API ]
  - Stores all             - llama-3.1-8b-instant
  - chat history           - OpenAI-compatible
  - by session ID          - >200 tokens/sec
```

---

## Features

- **Conversation memory.** Each message is stored in PostgreSQL, and the full session history is sent with every model call, so the assistant can refer back to things you said earlier.
- **Sessions.** Every client gets its own UUID session token, so multiple people can chat at the same time without their histories mixing.
- **Rate limiting.** An in-memory, per-IP sliding window caps each client at 5 requests a minute and returns a 429 once they go over.
- **Cloud inference.** Requests go to Groq's `llama-3.1-8b-instant` over its OpenAI-compatible API, so there's no local GPU to keep alive.
- **Parameterized queries.** Every SQL statement uses `%s` placeholders instead of string formatting, which keeps user input out of the query itself.
- **Streamlit frontend.** A simple chat UI with a session-info sidebar that handles the 429 case without breaking.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Frontend UI | Streamlit |
| LLM Inference | Groq Cloud (`llama-3.1-8b-instant`) |
| Persistence | PostgreSQL via `psycopg2-binary` |
| HTTP Client | httpx |
| Validation | Pydantic v2 |
| Config | python-dotenv |

---

## Project Structure

```
stateful-ai-gateway/
├── main.py            # FastAPI backend: chat endpoint, rate limiter, Groq call
├── app.py             # Streamlit frontend: chat UI, session handling
├── database.py        # PostgreSQL layer: init, save, and read chat history
├── requirements.txt   # Python dependencies
├── .env               # API keys, never committed (see .gitignore)
└── .gitignore
```

---

## Local Setup

**1. Clone the repo**
```bash
git clone https://github.com/Ogirala-Uday-Venkat-Rahul/stateful-ai-gateway.git
cd stateful-ai-gateway
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
You can get a free key at [console.groq.com](https://console.groq.com).

**4. Initialize the database**
```bash
python database.py init
```

**5. Start the FastAPI backend**
```bash
uvicorn main:app --reload
```

**6. Start the Streamlit frontend** (in a second terminal)
```bash
streamlit run app.py
```

The frontend runs at `http://localhost:8501`, and the backend API docs are at `http://localhost:8000/docs`.

---

## API Reference

### `POST /chat`

Takes a message and a session ID, returns the assistant's reply.

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

**Why Groq instead of running a model locally?**
My machine has a 4GB GPU, which isn't enough to run a model under steady load without crashing. Groq handles the inference instead, returns tokens quickly, and its API follows the OpenAI format, so the client code stays simple.

**Why PostgreSQL instead of SQLite?**
SQLite writes to a local file, and on most cloud hosts that file is wiped on every restart, so the chat history wouldn't survive a redeploy. Postgres runs as a managed service (I used Neon's free tier) and keeps the data between restarts. All the database code lives in `database.py`, so moving from SQLite to Postgres only changed that one file.

**Why a sliding window for rate limiting?**
A fixed window resets on a clock boundary, so a client can send 5 requests just before the reset and 5 more right after and slip 10 through in a second. A sliding window checks the actual last 60 seconds on every request, which closes that gap.
