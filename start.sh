#!/usr/bin/env sh
# start.sh: runs FastAPI and Streamlit in parallel

# 1) Launch FastAPI
uvicorn app.fastapi_app:app \
    --host 0.0.0.0 --port 8000 &

# 2) Launch Streamlit UI
streamlit run app/streamlit_app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
