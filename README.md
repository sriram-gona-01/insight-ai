# Insight AI

**On-prem PPT/PDF RAG assistant** using Qwen2.5-VL, pgvector, FastAPI & Streamlit.

## 🏗️ Project Structure

```nginx
.
├── app/
│ ├── extractor.py
│ ├── summarizer.py
│ ├── indexer.py
│ ├── retriever.py
│ ├── qa.py
│ ├── fastapi_app.py
│ ├── streamlit_app.py
├── Dockerfile
├── start.sh
├── requirements.txt
├── .gitignore
└── README.md
```


## ⚙️ Prerequisites

- Docker & Docker Compose (or plain Docker)
- A running Postgres 14 + pgvector (see `.env` for credentials)
- Ollama server with `qwen2.5vl:latest` pulled

## 🚀 Running with Docker

1. Build the image:

   ```bash
   docker build -t insight-ai:latest .
