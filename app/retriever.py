import os
import sys
import subprocess
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer



DATABASE_URL="postgresql://localhost:5432/rfp_rag"

EMBED_MODEL = "sentence-transformers/msmarco-bert-base-dot-v5"


TABLE_NAME = "documents"

# Ollama CLI settings for generation:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")
OLLAMA_CMD   = [
    "ollama", "run", OLLAMA_MODEL
]


# ─── Step A: Retrieval ─────────────────────────────────────────────────────

def retrieve(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed the question, query pgvector, and return the top_k chunks.
    """
    # 1) Embed the question
    embedder = SentenceTransformer(EMBED_MODEL)
    q_emb = embedder.encode([question])[0].tolist()

    # 2) Connect & register VECTOR type
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    cur = conn.cursor()

    # 3) Retrieve by cosine similarity (<=>)
    cur.execute(f"""
        SELECT id, text
          FROM {TABLE_NAME}
         ORDER BY embedding <=> %s::vector
         LIMIT %s
    """, (q_emb, top_k))

    rows = cur.fetchall()
    conn.close()

    # 4) Return as list of dicts
    return [{"id": r[0], "text": r[1]} for r in rows]

