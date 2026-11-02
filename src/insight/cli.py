"""The `insight` command line."""

import logging
from pathlib import Path
from typing import Annotated

import psycopg
import typer
from psycopg_pool import PoolTimeout

from insight import __version__
from insight.config import Settings
from insight.embed.text import get_text_embedder
from insight.ingest.pipeline import InvalidDocument, ingest_file
from insight.store import db

app = typer.Typer(help="Insight AI: question answering over slide decks and PDFs.")
db_app = typer.Typer(help="Manage the database.")
docs_app = typer.Typer(help="Inspect ingested documents.")
app.add_typer(db_app, name="db")
app.add_typer(docs_app, name="docs")

# Connection failures are reported once by the commands below, not per pool retry.
logging.getLogger("psycopg.pool").setLevel(logging.CRITICAL)

DB_HELP = "Cannot use the database. Start it with `make db`, then run `insight db init`."


@app.callback()
def main() -> None:
    """Insight AI: question answering over slide decks and PDFs."""


@app.command()
def version() -> None:
    """Print the version and the configured data directory."""
    settings = Settings()
    typer.echo(f"insight-ai {__version__}")
    typer.echo(f"data dir: {settings.data_dir}")


@db_app.command("init")
def db_init() -> None:
    """Create the extension, tables, and indexes. Safe to run repeatedly."""
    settings = Settings()
    try:
        db.init_schema(settings.database_url, settings.embedding_dim)
    except psycopg.OperationalError as e:
        typer.echo(f"Cannot reach the database. Start it with `make db`.\n{e}", err=True)
        raise typer.Exit(1) from e
    typer.echo("Database ready.")


@app.command()
def ingest(
    paths: Annotated[
        list[Path], typer.Argument(exists=True, dir_okay=False, help="PPTX or PDF files")
    ],
) -> None:
    """Render, extract, embed, and store documents. Already-ingested files are skipped."""
    settings = Settings()
    embedder = get_text_embedder(
        settings.embedding_model,
        settings.embedding_revision,
        settings.embedding_dim,
        settings.embedding_device,
    )
    failed = False
    try:
        pool = db.get_pool(settings.database_url)
        for path in paths:
            try:
                result = ingest_file(path, settings, pool, embedder)
            except InvalidDocument as e:
                typer.echo(f"{path.name}: rejected: {e}", err=True)
                failed = True
                continue
            if result.error:
                typer.echo(f"{path.name}: failed: {result.error}", err=True)
                failed = True
            elif result.skipped:
                typer.echo(f"{path.name}: skipped, already {result.status} ({result.doc_id})")
            else:
                typer.echo(f"{path.name}: ready ({result.doc_id})")
    except (psycopg.Error, PoolTimeout) as e:
        typer.echo(f"{DB_HELP}\n{e}", err=True)
        raise typer.Exit(1) from e
    if failed:
        raise typer.Exit(1)


@docs_app.command("list")
def docs_list() -> None:
    """List documents with their status and slide counts."""
    settings = Settings()
    try:
        documents = db.list_documents(db.get_pool(settings.database_url))
    except (psycopg.Error, PoolTimeout) as e:
        typer.echo(f"{DB_HELP}\n{e}", err=True)
        raise typer.Exit(1) from e
    if not documents:
        typer.echo("No documents.")
    for d in documents:
        line = f"{d.id}  {d.status:<10}  {d.n_slides or 0:>4} slides  {d.filename}"
        typer.echo(f"{line}  [{d.error}]" if d.error else line)
