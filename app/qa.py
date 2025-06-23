import os
import sys
import subprocess
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from app.retriever import retrieve

DATABASE_URL="postgresql://localhost:5432/rfp_rag"

EMBED_MODEL = "sentence-transformers/msmarco-bert-base-dot-v5"


TABLE_NAME = "documents"

# Ollama CLI settings for generation:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")
OLLAMA_CMD   = [
    "ollama", "run", OLLAMA_MODEL
]


# ─── Step B: Generation via Ollama CLI ──────────────────────────────────────

def generate_answer(question: str, contexts: list[dict]) -> str:
    """
    Given the question and retrieved contexts, call Ollama CLI to generate an answer.
    """
    # 1) Build the prompt
    prompt = "You are a helpful dashboard and flowdiagram assistant.\n\n"
    for i, c in enumerate(contexts, start=1):
        prompt += f"[Context {i}]\n{c['text']}\n\n"
    prompt += f"User Question: {question}\nAssistant Answer:"

    # 2) Invoke Ollama CLI
    proc = subprocess.run(
        OLLAMA_CMD + [prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 3) Error handling
    if proc.returncode != 0:
        raise RuntimeError(f"Ollama CLI failed:\n{proc.stderr}")

    # 4) Decode and return
    return proc.stdout.strip()




def answer(question: str, top_k: int = 5) -> str:
    """
    Retrieve the top_k chunks and generate an answer.
    """
    ctxs = retrieve(question, top_k=top_k)
    return generate_answer(question, ctxs)