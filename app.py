import streamlit as st
import httpx
import uuid

try:
    BACKEND_URL = st.secrets["BACKEND_URL"]
except (KeyError, FileNotFoundError):
    BACKEND_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(page_title="AI Gateway Platform", page_icon="🤖", layout="centered")
st.title("🤖 Core AI Gateway Interface")
st.caption("Stateful Session Management & sliding-window IP Rate Limiter Demo")

# 1. Automate Session ID Management using browser session state
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"

# Local memory array to show text instantly on screen re-renders
if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = []

# Sidebar panel tracking system analytics for presentation
with st.sidebar:
    st.header("Architectural State Diagnostics")
    st.metric(label="Active Session ID", value=st.session_state.session_id)
    st.markdown("""
    ---
    ### Infrastructure Specs:
    * **Frontend:** Streamlit 
    * **Backend API:** FastAPI (Uvicorn Async Loop)
    * **Memory Layer:** PostgreSQL (Neon, cloud-hosted)
    * **Inference Engine:** Groq Cloud (Llama 3.1)
    * **Defensive Boundary:** 5 req / min sliding window
    """)
    if st.button("Reset Session State"):
        st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
        st.session_state.ui_messages = []
        st.rerun()

# 2. Render chronological context on screen
for msg in st.session_state.ui_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 3. Capture user message submissions
if prompt := st.chat_input("Send a message to the engine..."):
    # Render user prompt instantly
    st.session_state.ui_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
        
    # Contact the FastAPI middleman pipeline
    with st.chat_message("assistant"):
        with st.spinner("Processing cloud inference tokens..."):
            payload = {
                "session_id": st.session_state.session_id,
                "message": prompt
            }
            try:
                with httpx.Client() as client:
                    response = client.post(BACKEND_URL, json=payload, timeout=45.0)
                
                if response.status_code == 200:
                    reply = response.json()["reply"]
                    st.write(reply)
                    st.session_state.ui_messages.append({"role": "assistant", "content": reply})
                elif response.status_code == 429:
                    error_detail = response.json().get("detail", "Too Many Requests")
                    st.error(f"🛡️ **Rate Limiter Shield Triggered:** {error_detail}")
                else:
                    st.error(f"Backend Returned Error ({response.status_code}): {response.text}")
                    
            except Exception as e:
                st.error(f"Unable to route packet to FastAPI backend server: {str(e)}")