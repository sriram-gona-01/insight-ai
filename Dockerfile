FROM python:3.11-slim-bookworm

ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-impress fonts-liberation fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.13.6

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY samples ./samples
RUN uv sync --locked --no-dev

EXPOSE 8000 8501
