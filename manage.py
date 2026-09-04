import typer

from assistant.knowledge_base import index
from assistant.scrape import fetch

app = typer.Typer(help="Maintenance commands for the healthcare assistant.")


@app.command()
def scrape() -> None:
    """Render the hospital website into knowledge/scraped/."""
    fetch.crawl()


@app.command()
def build_index() -> None:
    """Embed the scraped corpus into the vector store."""
    index.build()


if __name__ == "__main__":
    app()
