# app/fastapi_app.py

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
from sentence_transformers import SentenceTransformer
from app.extractor import extract_documents
from app.summarizer    import summarize_image
from app.indexer import init_db, build_index
from app.retriever import retrieve
from app.qa import generate_answer, answer

app = FastAPI(
    title="Insight AI",
    description="On-prem RAG for PPT/PDF dashboards & diagrams",
    version="0.1.0"
)


# ─── Payload model for /query ─────────────────────────────────────────────
class QueryPayload(BaseModel):
    question: str
    top_k:    int = 5


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Insight AI backend is running"}


@app.post("/upload", tags=["Index"], response_model=List[str])
async def upload(file: UploadFile = File(...)):
    """
    1) Save uploaded file to /tmp
    2) Extract & summarize chunks
    3) Embed & index into Postgres+pgvector
    4) Return list of chunk IDs
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file upload")

    # 1) write to temp file
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(data)

    # 2) extract & summarize
    docs = extract_documents(tmp_path)
    if not docs:
        raise HTTPException(400, "No text/image chunks found in file")

    for d in docs:
        # text summarization is a no-op by default
        d["text"] = summarize_image(d["text"])

    # 3) embed & index
    texts = [d["text"] for d in docs]
    EMBED_MODEL = "sentence-transformers/msmarco-bert-base-dot-v5"
    embedder = SentenceTransformer(EMBED_MODEL)
    embeddings = embedder.encode(texts, convert_to_numpy=True).tolist()

    conn = init_db()
    build_index(conn, docs, embeddings)
    conn.close()

    # return the list of IDs so client can track what was ingested
    return [d["id"] for d in docs]


@app.post("/query")
async def query(payload: QueryPayload):
    """
    Answer questions against the pre-built index.
    You must have already run the indexer offline.
    """
    try:
        contexts = retrieve(payload.question, top_k=payload.top_k)
        ans      = answer(payload.question, top_k=payload.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QA failed: {e}")
    return {"answer": ans, "contexts": contexts}
