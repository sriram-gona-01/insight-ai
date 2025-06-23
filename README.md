# Insight AI

> **On-prem RAG assistant** for PPTX/PDF dashboards & diagrams, with Qwen-VL vision–language, pgvector, FastAPI & Streamlit.

---

## 🔍 Overview

Insight AI lets you upload PowerPoint decks or PDFs containing slides, flow-charts, dashboards or architectural diagrams, and immediately query them in natural language. Everything runs locally:

- ✅ **Data never leaves your network**  
- 🤖 **Vision + OCR → Qwen2.5-VL** generates image summaries  
- 📄 **Native text, tables & charts** are extracted in chunks  
- 📦 **Dense embeddings** stored in Postgres + pgvector  
- 🔄 **Hybrid retrieval → MMR (top K contexts)**  
- 🗣️ **Generation** via Ollama LLM (Qwen or Llama)  
- 🌐 **FastAPI** backend with `/upload` & `/query` endpoints  
- 💬 **Streamlit** front-end with ChatGPT-style UI  

---

## 📦 Tech Stack

| Layer             | Technology                            |
| ----------------- | ------------------------------------- |
| Extraction        | python-pptx, pdfplumber, Pillow       |
| Summarization     | Qwen2.5-VL via Ollama CLI             |
| Embeddings        | Sentence-Transformers (msmarco-bert)  |
| Vector Store      | Postgres 14 + pgvector extension      |
| Retrieval         | Postgres vector `<=>` operator        |
| LLM Generation    | Ollama Qwen2.5-VL or Llama 3.2-vision |
| API               | FastAPI + Uvicorn                     |
| UI                | Streamlit                             |
| Config management | Pydantic BaseSettings + python-dotenv |
| Containerization  | Docker + Docker Compose               |

---

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

1. **Git** & **VS Code** (or your IDE)
2. **Docker** & **docker-compose** (optional, but recommended)
3. **Postgres 14** with the **pgvector** extension
4. **Ollama** installed & `qwen2.5vl:latest` (or your LLM) pulled

---

## 🚀 Quickstart (Local, No Docker)

1. **Clone & enter**
   ```bash
   git clone git@github.com:<you>/insight-ai.git
   cd insight-ai
   ```

2. **Create & activate** a Python venv
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Create** a db in pgvector file at project root (add to `.gitignore`):
   ```
   DATABASE_URL=postgresql://<user>:<password>/<db_name>
   ```

5. **Ensure** your Postgres has pgvector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

6. **Pull** your Ollama model & **serve** it:
   ```bash
   ollama pull qwen2.5vl:latest
   ollama serve
   ```

7. **Start** the FastAPI + Streamlit UIs:
   ```bash
   # in one terminal
   uvicorn app.fastapi_app:app --reload --port 8000

   # in another terminal
   streamlit run app/streamlit_app.py --server.port 8501
   ```

8. **Browse**
   - FastAPI OpenAPI: http://localhost:8000/docs
   - Streamlit Chat:     http://localhost:8501

---

## 🐋 Running with Docker Compose

1. **Ensure** Docker & Docker Compose are installed.

2. **Edit** Database URL with your Postgres creds.

3. **Bring up** the stack:
   ```bash
   docker-compose up --build
   ```

4. **Access** same ports as above.

---

## 📝 Usage

1. **Upload** a PPTX/PDF/TXT in the UI.
2. Wait for **“Indexed … chunks🎉”**.
3. **Ask** questions in the chat box:
   - “What trend do you see in slide 3?”
   - “Summarize the architecture diagram.”
   - “List all the issues shown on the dashboard.”

4. Scroll through **past messages** just like ChatGPT.

---

## 🔧 Configuration

All runtime settings live in `app/settings.py`, sourced from:

- **Environment variables** (e.g. on server or CI)


| Variable       | Default                                      | Purpose                             |
| -------------- | -------------------------------------------- | ----------------------------------- |
| `DATABASE_URL` | _required_                                   | Postgres connection URL             |
| `EMBED_MODEL`  | sentence-transformers/msmarco-bert-base-dot-v5 | Embedding model identifier          |

---

## 🤝 Contributing

1. Fork & clone
2. Create a feature branch
3. Commit & push
4. Open a PR against `main`

Please ensure new dependencies are added to `requirements.txt` and that you update this README as needed.

---

*Happy local RAG-ing!* 🚀

   

   
