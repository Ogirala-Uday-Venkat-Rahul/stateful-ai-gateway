import os
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx
import database  # PostgreSQL (Neon) data layer

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI()

class ChatRequest(BaseModel):
    session_id: str
    message: str

# Groq (OpenAI-compatible API)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set in the environment")
MODEL_NAME = "llama-3.1-8b-instant"

# Sliding-window rate limit: at most MAX_REQUESTS per client per RATE_LIMIT_WINDOW seconds.
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS = 5
request_tracker = {}    # in-memory: client IP -> list of recent request timestamps

@app.post("/chat")
async def chat(request_req: ChatRequest, fastapi_request: Request):
    # Identify the client by IP. Behind a proxy the real client is the first entry
    # of the X-Forwarded-For chain; otherwise use the direct connection IP.
    forwarded_for = fastapi_request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = fastapi_request.client.host
    now = time.time()

    if client_ip not in request_tracker:
        request_tracker[client_ip] = []

    # Drop timestamps older than the window so we only count recent requests.
    request_tracker[client_ip] = [t for t in request_tracker[client_ip] if now - t < RATE_LIMIT_WINDOW]

    # Reject if the client has already used its allowance in the current window.
    if len(request_tracker[client_ip]) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {MAX_REQUESTS} requests per minute allowed."
        )

    # Otherwise record this request's timestamp.
    request_tracker[client_ip].append(now)

    # Save the incoming message.
    database.save_message(request_req.session_id, "user", request_req.message)

    # Load the full session history to send back as context.
    chat_history = database.get_chat_history(request_req.session_id)

    # Build the chat-completion request.
    groq_payload = {
        "model": MODEL_NAME,
        "messages": chat_history,
        "max_tokens": 512,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Call Groq.
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GROQ_API_URL, json=groq_payload, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Groq API error: {e.response.text}")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Could not reach the Groq API.")

    # Extract the reply text from the standard response shape.
    response_data = response.json()
    ai_reply = response_data["choices"][0]["message"]["content"]

    # Save the assistant's reply.
    database.save_message(request_req.session_id, "assistant", ai_reply)

    return {"reply": ai_reply}
