"""The `insight` command line."""

import typer

from insight import __version__
from insight.config import Settings

app = typer.Typer(help="Insight AI: question answering over slide decks and PDFs.")


@app.callback()
def main() -> None:
    """Keep subcommands explicit, even while there is only one."""


@app.command()
def version() -> None:
    """Print the version and the configured data directory."""
    settings = Settings()
    typer.echo(f"insight-ai {__version__}")
    typer.echo(f"data dir: {settings.data_dir}")
