import streamlit as st
import httpx
import uuid

try:
    BACKEND_URL = st.secrets["BACKEND_URL"]
except (KeyError, FileNotFoundError):
    BACKEND_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(page_title="Stateful AI Chat Gateway", page_icon="🤖", layout="centered")
st.title("Stateful AI Chat Gateway")
st.caption("Chat with conversation memory, backed by FastAPI, PostgreSQL, and Groq.")

# Give each browser session its own ID so separate users don't share history.
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"

# Keep the visible messages in session state so they survive Streamlit reruns.
if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = []

# Sidebar: current session and the stack behind it.
with st.sidebar:
    st.header("Session")
    st.metric(label="Session ID", value=st.session_state.session_id)
    st.markdown("""
    ---
    ### Stack
    * **Frontend:** Streamlit
    * **Backend:** FastAPI (Uvicorn)
    * **Database:** PostgreSQL (Neon)
    * **Model:** Groq (Llama 3.1 8B)
    * **Rate limit:** 5 requests/min per IP (sliding window)
    """)
    if st.button("Reset Session"):
        st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
        st.session_state.ui_messages = []
        st.rerun()

# Render the conversation so far.
for msg in st.session_state.ui_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Handle a new message.
if prompt := st.chat_input("Send a message"):
    # Show the user's message immediately.
    st.session_state.ui_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Call the backend.
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
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
                    st.error(f"**Rate limit reached:** {error_detail}")
                else:
                    st.error(f"Backend error ({response.status_code}): {response.text}")

            except Exception as e:
                st.error(f"Could not reach the backend: {str(e)}")
