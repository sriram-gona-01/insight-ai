"""Streamlit UI: a thin client of the API."""

import time

import httpx
import streamlit as st

from insight.config import Settings
from insight.retrieve.pipelines import PIPELINES

settings = Settings()
api = httpx.Client(base_url=settings.api_url, timeout=settings.llm_timeout_seconds + 30)

STATUS_POLL_SECONDS = 1.0
FINISHED = {"ready", "failed"}

st.set_page_config(page_title="Insight AI", layout="wide")
st.title("Insight AI")
st.caption("Ask questions about your slide decks and PDFs. Answers cite the slides they use.")


@st.cache_data(show_spinner=False)
def slide_image(slide_id: str) -> bytes | None:
    response = api.get(f"/slides/{slide_id}/image")
    return response.content if response.status_code == 200 else None


def show_health() -> None:
    try:
        health = api.get("/health").json()
    except httpx.HTTPError:
        st.error(f"Can't reach the API at {settings.api_url}.")
        st.stop()
    if not health["llm"]:
        st.warning(
            f"The model `{health['model']}` isn't reachable. "
            f"On the host, run `ollama pull {health['model']}`. Ingest still works."
        )


def upload(file: "st.runtime.uploaded_file_manager.UploadedFile") -> None:
    response = api.post("/documents", files={"file": (file.name, file.getvalue())})
    if response.status_code != 202:
        st.error(f"{file.name}: {response.json().get('detail', response.text)}")
        return
    created = response.json()
    if created["skipped"]:
        st.info(f"{file.name} is already {created['status']}.")
        return
    with st.status(f"Processing {file.name}", expanded=True) as box:
        while True:
            document = api.get(f"/documents/{created['id']}").json()
            box.update(label=f"{file.name}: {document['status']}")
            if document["status"] in FINISHED:
                break
            time.sleep(STATUS_POLL_SECONDS)
        if document["status"] == "failed":
            box.update(state="error")
            st.error(document["error"])
        else:
            box.update(state="complete")


def show_result(result: dict) -> None:
    st.markdown(result["answer"])
    if result["citations"]:
        st.caption("Cited slides")
        columns = st.columns(min(len(result["citations"]), 4))
        for i, citation in enumerate(result["citations"]):
            with columns[i % len(columns)]:
                image = slide_image(citation["slide_id"])
                label = f"{citation['doc']}, slide {citation['slide_no']}"
                if image:
                    st.image(image, caption=label)
                    with st.expander("Expand"):
                        st.image(image)
                else:
                    st.write(label)
    elif not result["abstained"]:
        st.caption("The model cited no slides for this answer, so check it carefully.")
    timings = "  ·  ".join(f"{k} {v:,.0f} ms" for k, v in result["timings_ms"].items())
    st.caption(f"{timings}  ·  {result['model']}")
    with st.expander("Retrieved slides"):
        for slide in result["retrieved"]:
            st.write(
                f"{slide['score']:.3f}  {slide['doc']}, slide {slide['slide_no']}: {slide['title']}"
            )


show_health()

with st.sidebar:
    st.header("Settings")
    pipeline = st.selectbox(
        "Pipeline", list(PIPELINES), format_func=lambda name: f"{name}: {PIPELINES[name]}"
    )
    top_k = st.slider("Slides to retrieve (top-k)", 1, 10, settings.default_top_k)
    context_format = st.selectbox("Context sent to the model", ["both", "text", "image"])

    st.header("Documents")
    files = st.file_uploader("Add PPTX or PDF", type=["pptx", "pdf"], accept_multiple_files=True)
    if files and st.button("Upload"):
        for file in files:
            upload(file)
    for document in api.get("/documents").json():
        name, remove = st.columns([4, 1])
        name.caption(
            f"{document['filename']}: {document['status']}, {document['n_slides'] or 0} slides"
        )
        if remove.button("✕", key=document["id"], help="Delete this document"):
            api.delete(f"/documents/{document['id']}")
            st.rerun()

if "history" not in st.session_state:
    st.session_state.history = []

for entry in st.session_state.history:
    with st.chat_message(entry["role"]):
        if entry["role"] == "user":
            st.markdown(entry["content"])
        else:
            show_result(entry["content"])

if question := st.chat_input("Ask about your documents"):
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("Searching slides and asking the model"):
        response = api.post(
            "/query",
            json={
                "question": question,
                "pipeline": pipeline,
                "top_k": top_k,
                "context_format": context_format,
            },
        )
        if response.status_code == 200:
            result = response.json()
            show_result(result)
            st.session_state.history.append({"role": "assistant", "content": result})
        else:
            st.error(response.json().get("detail", response.text))
