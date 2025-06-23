import streamlit as st
import requests

# ─── CONFIG ────────────────────────────────────────────────────────────────
API_HOST   = "http://localhost:8000"
UPLOAD_URL = f"{API_HOST}/upload"
QUERY_URL  = f"{API_HOST}/query"

# ─── PAGE SETUP ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Insight AI ",
    page_icon="🤖",
    layout="centered",
)

st.markdown(
    """
    <div style="text-align:center">
      <h1>🤖 Insight AI</h1>
      <p>Your on-prem Q&A assistant</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── FILE UPLOAD ───────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📂 Upload PPT/PDF/TXT to index", 
    type=["pptx","pdf","txt"]
)
if uploaded_file:
    with st.spinner("Indexing…"):
        response = requests.post(
            UPLOAD_URL,
            files={"file": (uploaded_file.name, uploaded_file.getvalue())},
        )
    if response.ok:
        st.success(f"Indexed {len(response.json())} chunks 🎉")
    else:
        st.error(f"Upload failed: {response.text}")

# ─── CHAT HISTORY ──────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []  # list of (role, message)

# display prior messages
for role, msg in st.session_state.history:
    st.chat_message(role).write(msg)

# ─── USER INPUT ────────────────────────────────────────────────────────────
query = st.chat_input("Start typing…")
if query:
    # record & display user message
    st.session_state.history.append(("user", query))
    st.chat_message("user").write(query)

    # call backend
    with st.spinner("Thinking…"):
        payload = {"question": query, "top_k": 5}
        resp = requests.post(QUERY_URL, json=payload)

    if resp.ok:
        answer = resp.json().get("answer", "").strip()
        st.session_state.history.append(("assistant", answer))
        st.chat_message("assistant").write(answer)
    else:
        st.session_state.history.append(("assistant", f"Error: {resp.text}"))
        st.chat_message("assistant").write(f"Error: {resp.text}")
