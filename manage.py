import typer

from assistant import evaluate as evaluation
from assistant.database import seed as database
from assistant.knowledge_base import index
from assistant.scrape import fetch

app = typer.Typer(help="Maintenance commands for the healthcare assistant.")


@app.command()
def seed() -> None:
    """Load data.sql into the hospital database."""
    database.seed()


@app.command()
def scrape() -> None:
    """Render the hospital website into knowledge/scraped/."""
    fetch.crawl()


@app.command()
def build_index() -> None:
    """Embed the scraped corpus into the vector store."""
    index.build()


@app.command()
def evaluate() -> None:
    """Score routing accuracy against the golden question set."""
    evaluation.run()


if __name__ == "__main__":
    app()
