CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          uuid PRIMARY KEY,
    filename    text NOT NULL,
    sha256      text NOT NULL UNIQUE,
    n_slides    integer,
    status      text NOT NULL CHECK (status IN
                    ('queued', 'rendering', 'extracting', 'embedding', 'ready', 'failed')),
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS slides (
    id          uuid PRIMARY KEY,
    doc_id      uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    slide_no    integer NOT NULL,
    image_path  text NOT NULL,
    title       text NOT NULL,
    text        text NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE (doc_id, slide_no)
);

CREATE TABLE IF NOT EXISTS chunks (
    id          uuid PRIMARY KEY,
    slide_id    uuid NOT NULL REFERENCES slides (id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('text', 'table', 'chart', 'notes')),
    text        text NOT NULL,
    embedding   vector({{embedding_dim}}) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_slide_id_idx ON chunks (slide_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
