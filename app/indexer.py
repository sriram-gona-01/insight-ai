# app/indexer_pgvector.py

import os
import sys
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from app.extractor import extract_documents

DATABASE_URL="postgresql://localhost:5432/insight_rag"
if not DATABASE_URL:
    raise RuntimeError("Please set the DATABASE_URL environment variable")

# Embedding model (ColBERT-style single-vector)
EMBED_MODEL = "sentence-transformers/msmarco-bert-base-dot-v5"

# The Postgres table name
TABLE_NAME  = "documents"

# ─── DB INITIALIZATION ─────────────────────────────────────────────────────

def init_db():
    """
    Connects and ensures the pgvector extension + documents table exist.
    """
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    with conn.cursor() as cur:
        # Enable pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        # Create the documents table if not exists
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id        TEXT PRIMARY KEY,
                text      TEXT NOT NULL,
                embedding VECTOR({SentenceTransformer(EMBED_MODEL).get_sentence_embedding_dimension()})
            );
        """)
    conn.commit()
    return conn



def build_index(file_path: str):
    """
    1) Extract chunks via extractor.extract_pptx
    2) Embed each chunk’s text
    3) Upsert into Postgres+pgvector
    """
    # 1) Extract
    docs = extract_documents(file_path)
    if not docs:
        print("No chunks extracted. Exiting.")
        return

    # 2) Embed
    embedder = SentenceTransformer(EMBED_MODEL)
    texts = [d["text"] for d in docs]
    embeddings = embedder.encode(texts, show_progress_bar=True)

    # 3) Upsert into Postgres
    conn = init_db()
    with conn.cursor() as cur:
        for d, vec in zip(docs, embeddings):
            cur.execute(f"""
                INSERT INTO {TABLE_NAME}(id, text, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                  SET text = EXCLUDED.text,
                      embedding = EXCLUDED.embedding;
            """, (d["id"], d["text"], vec.tolist()))
    conn.commit()
    conn.close()

    print(f"✅ Indexed {len(docs)} chunks into `{TABLE_NAME}`.")




