import os
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx
import database  # Your SQLite data helper layer

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI()

class ChatRequest(BaseModel):
    session_id: str
    message: str

# Groq Cloud Configuration (OpenAI Compatible Architecture)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("CRITICAL ENVIRONMENT ERROR: GROQ_API_KEY is missing from system memory!")
MODEL_NAME = "llama-3.1-8b-instant"  # Supercharged, hyper-fast cloud open model

# 🛡️ SLIDING-WINDOW RATE LIMIT CONFIGURATION
RATE_LIMIT_WINDOW = 60  # Timeframe in seconds (1 minute)
MAX_REQUESTS = 5        # Allowed hits per client per window
request_tracker = {}    # Memory structure -> Key: Client IP, Value: List of timestamps

@app.post("/chat")
async def chat(request_req: ChatRequest, fastapi_request: Request):
    # Step 1: Capture Client Fingerprint (IP Address)
    client_ip = fastapi_request.client.host
    now = time.time()
    
    if client_ip not in request_tracker:
        request_tracker[client_ip] = []
        
    # Sliding Window Clean-up: Evict timestamps older than 60 seconds
    request_tracker[client_ip] = [t for t in request_tracker[client_ip] if now - t < RATE_LIMIT_WINDOW]
    
    # Core Resource Defense Evaluation
    if len(request_tracker[client_ip]) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {MAX_REQUESTS} requests per minute allowed."
        )
        
    # Accept Request: Log the current active timestamp
    request_tracker[client_ip].append(now)

    # Step 2: Log Incoming Message to SQLite File 
    database.save_message(request_req.session_id, "user", request_req.message)
    
    # Step 3: Extract Entire Chronological Message History for context
    chat_history = database.get_chat_history(request_req.session_id)
    
    # Step 4: Construct Standard Chat Completion Payload
    groq_payload = {
        "model": MODEL_NAME,
        "messages": chat_history,
        "stream": False
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 5: Perform Network Connection to the Cloud Pipeline
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GROQ_API_URL, json
            =groq_payload, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Cloud Engine Error: {e.response.text}")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Cloud Infrastructure Gateway unreachable.")

    # Step 6: Parse the Token Content from standard JSON structure
    response_data = response.json()
    ai_reply = response_data["choices"][0]["message"]["content"]
    
    # Step 7: Commit AI Reply to persistent database
    database.save_message(request_req.session_id, "assistant", ai_reply)
    
    return {"reply": ai_reply}